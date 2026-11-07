"""
routers/eval.py — Agent IQ: offline accuracy evaluation endpoint.

GET  /admin/eval/status   → last cached result (or empty if never run)
POST /admin/eval/run      → run offline eval suite, cache & return result
                            (admin-only via master API key)

Runs test_accuracy.run() directly in a thread executor — no subprocess
overhead and no Oracle-client hang risk.
"""
import io
import os
import sys
import json
import time
import logging
import asyncio
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

log = logging.getLogger("router.eval")

router = APIRouter(prefix="/admin/eval", tags=["eval"])

_CACHE_PATH = Path("data/last_eval.json")
_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

_MASTER_KEY = os.getenv("API_KEY", "").strip()


def _require_admin(request: Request) -> None:
    if not _MASTER_KEY:
        return  # dev mode
    key = (
        request.headers.get("x-api-key")
        or request.headers.get("X-Api-Key")
        or ""
    )
    if key != _MASTER_KEY:
        raise HTTPException(403, "هذا الإجراء يتطلب صلاحيات المدير — X-Api-Key مطلوب")


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:
        log.warning("eval cache write failed: %s", e)


def _run_eval_sync() -> dict:
    """
    Import test_accuracy (cached after first import) and call run().
    Returns structured result dict.
    """
    # Ensure env is set before importing
    os.environ.setdefault("LEARNING_FORCE_SQLITE", "1")
    os.environ.setdefault("SCHEMA_FILE", "justclick_comments.sql")
    os.environ["EVAL_NO_LLM"] = "1"  # skip LLM fallback in classify_intent

    # Capture stdout from run()
    buf = io.StringIO()
    t0 = time.perf_counter()

    try:
        import test_accuracy as ta

        with redirect_stdout(buf):
            ta.run(live=False)

    except Exception as e:
        import traceback
        log.error("[EVAL] run() raised: %s\n%s", repr(e), traceback.format_exc())
        raise
    finally:
        os.environ.pop("EVAL_NO_LLM", None)  # restore normal LLM behavior

    elapsed = round(time.perf_counter() - t0, 2)
    output = buf.getvalue()

    return _parse_output(output, elapsed)


def _parse_output(stdout: str, elapsed: float) -> dict:
    """Parse printed output from run() into structured dict."""
    import re

    domains: dict[str, dict] = {}
    score = 0.0
    passed = failed = skipped = tested = total = 0
    threshold = 90
    result_str = "UNKNOWN"

    for line in stdout.splitlines():
        line = line.strip()

        # Domain breakdown: "  accounting    20P   0F   0S"
        m = re.match(r"(\w+)\s+(\d+)P\s+(\d+)F\s+(\d+)S", line)
        if m:
            domains[m.group(1)] = {
                "pass": int(m.group(2)),
                "fail": int(m.group(3)),
                "skip": int(m.group(4)),
            }
            continue

        if line.startswith("PASS:"):
            passed = int(re.search(r"\d+", line).group())
        elif line.startswith("FAIL:"):
            failed = int(re.search(r"\d+", line).group())
        elif line.startswith("SKIP:"):
            skipped = int(re.search(r"\d+", line).group())
        elif line.startswith("TESTED:"):
            m2 = re.search(r"(\d+)/(\d+)", line)
            if m2:
                tested = int(m2.group(1))
                total  = int(m2.group(2))
        elif line.startswith("THRESHOLD:"):
            m4 = re.search(r"\d+", line)
            if m4:
                threshold = int(m4.group())
        elif line.startswith("RESULT:"):
            result_str = "PASS" if "PASS" in line else "FAIL"
            m5 = re.search(r"([\d.]+)%", line)
            if m5:
                score = float(m5.group(1))

    if not score and tested:
        score = round(passed / tested * 100, 1)

    return {
        "score":     score,
        "pass":      passed,
        "fail":      failed,
        "skip":      skipped,
        "tested":    tested,
        "total":     total,
        "threshold": threshold,
        "result":    result_str,
        "elapsed_s": elapsed,
        "domains":   domains,
        "run_at":    datetime.now().isoformat(timespec="seconds"),
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/status")
async def eval_status():
    """Return last cached eval result. Empty dict if never run."""
    return _load_cache()


@router.post("/run")
async def eval_run(request: Request):
    """Run offline eval suite (admin only). Returns structured result."""
    _require_admin(request)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_eval_sync)
    except Exception as e:
        import traceback
        log.error("[EVAL] endpoint error: %s\n%s", repr(e), traceback.format_exc())
        raise HTTPException(500, f"eval failed: {type(e).__name__}: {e}")

    _save_cache(result)
    log.info("[EVAL] score=%.1f%% pass=%d fail=%d skip=%d elapsed=%.1fs",
             result["score"], result["pass"], result["fail"],
             result["skip"], result["elapsed_s"])
    return result
