"""
token_tracker.py — Per-user daily token budget tracker.

SQLite-backed.  Resets at midnight.  Thread-safe via WAL + BEGIN IMMEDIATE.
Called from llm_client after every LLM response, and from the pipeline to
gate requests before they hit the LLM.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import date
from pathlib import Path

log = logging.getLogger("token_tracker")

_DB_PATH = Path(__file__).parent / "data" / "learning.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=5, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _ensure_table():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ai_token_usage (
                user_id   TEXT NOT NULL,
                day       TEXT NOT NULL,           -- YYYY-MM-DD
                prompt    INTEGER DEFAULT 0,
                completion INTEGER DEFAULT 0,
                calls     INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, day)
            )
        """)
        c.commit()


_ensure_table()


def today() -> str:
    return date.today().isoformat()


# ── Write ──────────────────────────────────────────────────────────

def track(user_id: str, prompt_tokens: int, completion_tokens: int):
    """Record token usage for user on today's date (atomic upsert)."""
    day = today()
    try:
        c = _conn()
        c.execute("BEGIN IMMEDIATE")
        c.execute("""
            INSERT INTO ai_token_usage (user_id, day, prompt, completion, calls)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(user_id, day) DO UPDATE SET
                prompt     = prompt     + excluded.prompt,
                completion = completion + excluded.completion,
                calls      = calls      + 1
        """, (user_id, day, prompt_tokens, completion_tokens))
        c.execute("COMMIT")
        c.close()
    except Exception as e:
        log.warning("[TOKEN] track failed for user=%s: %s", user_id, e)


# ── Read ───────────────────────────────────────────────────────────

def get_today_usage(user_id: str) -> dict:
    """Return today's token usage for user."""
    day = today()
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT prompt, completion, calls FROM ai_token_usage WHERE user_id=? AND day=?",
                (user_id, day),
            ).fetchone()
        if row:
            prompt, completion, calls = row
            return {
                "prompt": prompt,
                "completion": completion,
                "total": prompt + completion,
                "calls": calls,
                "day": day,
            }
    except Exception as e:
        log.debug("[TOKEN] read failed: %s", e)
    return {"prompt": 0, "completion": 0, "total": 0, "calls": 0, "day": day}


def check_budget(user_id: str, budget: int) -> tuple[bool, int, int]:
    """
    Check if user has remaining budget.
    Returns (allowed, used_today, remaining).
    budget=0 means unlimited.
    """
    if budget <= 0:
        return True, 0, -1   # unlimited

    usage = get_today_usage(user_id)
    used = usage["total"]
    remaining = max(0, budget - used)
    return remaining > 0, used, remaining


def get_usage_summary(user_id: str, budget: int) -> dict:
    """Full summary dict for API response."""
    usage = get_today_usage(user_id)
    used = usage["total"]
    remaining = max(0, budget - used) if budget > 0 else -1
    pct = round(used / budget * 100, 1) if budget > 0 else 0
    return {
        "used_today":  used,
        "budget":      budget,
        "remaining":   remaining,
        "pct_used":    pct,
        "calls_today": usage["calls"],
        "unlimited":   budget <= 0,
    }
