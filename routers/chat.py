"""
routers/chat.py — Main chat endpoint using the ERP Intelligence Pipeline.
"""
import re
import csv
import io
import logging
import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import List, Optional

from pipeline import process_question, PipelineResult
from llm_client import get_usage, _get_provider, set_provider
from sql_safety import get_audit_log, get_audit_stats
from memory import get_session_stats, clear_session, get_session
from schema_loader import get_schema_context
from query_templates import list_templates
from cache import get_all_stats as get_cache_stats, invalidate_all, sql_cache, dash_cache
from company_manager import get_user_companies

log = logging.getLogger("chat")

router = APIRouter(prefix="/chat", tags=["chat"])


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    company_code: str = "1"
    fiscal_year: str  = "2024"
    branch_id: str    = "0"
    user_id: str      = "web_user"
    history: List[HistoryMessage] = []

    @field_validator("question")
    @classmethod
    def question_max_length(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("السؤال لا يمكن أن يكون فارغاً")
        if len(v) > 2000:
            raise ValueError("السؤال طويل جداً — الحد الأقصى 2000 حرف")
        return v.strip()

    @field_validator("history")
    @classmethod
    def history_max_length(cls, v):
        if len(v) > 20:
            return v[-20:]
        return v


class ChatResponse(BaseModel):
    answer: str
    sql_generated: str
    row_count: int
    method: str = ""
    template_used: str = ""
    execution_time_ms: int = 0
    chart_data: Optional[dict] = None
    widgets: Optional[list] = None


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]

        result = await process_question(
            question=req.question,
            user_id=req.user_id,
            company_code=req.company_code,
            fiscal_year=req.fiscal_year,
            history=history,
        )

        return ChatResponse(
            answer=result.answer,
            sql_generated=result.sql,
            row_count=result.row_count,
            method=result.method,
            template_used=result.template_used,
            execution_time_ms=result.execution_time_ms,
            chart_data=result.chart_data,
            widgets=result.widgets,
        )
    except Exception as e:
        logging.error(f"[CHAT] Error: {e}\n{traceback.format_exc()}")
        err = str(e)
        if "429" in err or "rate_limit" in err.lower() or "resourceexhausted" in err.lower():
            wait = re.search(r'try again in (\d+m[\d.]+s)', err)
            wait_msg = f" (انتظر {wait.group(1)})" if wait else ""
            raise HTTPException(
                status_code=429,
                detail=f"تم تجاوز حد الاستخدام المجاني — حاول بعد قليل{wait_msg}"
            )
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ — حاول إعادة صياغة السؤال بشكل أوضح."
        )


# ── Usage & Provider endpoints ─────────────────────────────────────

@router.get("/usage")
async def usage():
    return get_usage()


@router.get("/provider")
async def get_provider():
    return {"provider": _get_provider()}


class ProviderRequest(BaseModel):
    provider: str


@router.post("/provider")
async def switch_provider(req: ProviderRequest):
    try:
        set_provider(req.provider)
        return {"provider": req.provider}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Admin / Debug endpoints ────────────────────────────────────────

@router.get("/schema-context")
async def get_context():
    ctx = get_schema_context()
    return {"length": len(ctx), "preview": ctx[:2000]}


@router.get("/audit")
async def audit(limit: int = 50):
    return {
        "stats": get_audit_stats(),
        "entries": get_audit_log(limit),
    }


@router.get("/memory-stats")
async def memory_stats():
    return get_session_stats()


@router.get("/templates")
async def templates(domain: str = None):
    return list_templates(domain)


# ── Clear memory endpoint ─────────────────────────────────────────

class ClearMemoryRequest(BaseModel):
    user_id: str = "web_user"


@router.post("/clear-memory")
async def clear_memory(req: ClearMemoryRequest):
    clear_session(req.user_id)
    log.info(f"[CHAT] Memory cleared for user={req.user_id}")
    return {"status": "ok", "message": "تم مسح الذاكرة بنجاح"}


# ── Export history endpoint ───────────────────────────────────────

@router.get("/export-history")
async def export_history(user_id: str = "web_user"):
    session = get_session(user_id)
    if not session.turns:
        raise HTTPException(status_code=404, detail="لا توجد محادثات لتصديرها")

    output = io.StringIO()
    output.write('﻿')  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    writer.writerow(["الدور", "المحتوى", "SQL", "النتائج", "الوقت"])

    import datetime
    for turn in session.turns:
        ts = datetime.datetime.fromtimestamp(turn.timestamp).strftime("%Y-%m-%d %H:%M:%S") if turn.timestamp else ""
        writer.writerow([
            "مستخدم" if turn.role == "user" else "مساعد",
            turn.content[:500],
            turn.sql,
            turn.row_count,
            ts,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=chat_history.csv"},
    )


# ── Cache endpoints ─────────────────────────────────────────────

@router.get("/cache-stats")
async def cache_stats():
    """إحصائيات الكاش لكل المستويات."""
    return get_cache_stats()


class CacheInvalidateRequest(BaseModel):
    tier: str = "all"  # all | sql | dashboard


@router.post("/cache/invalidate")
async def cache_invalidate(req: CacheInvalidateRequest):
    """إبطال الكاش — يمسح البيانات المخزنة مؤقتاً."""
    if req.tier == "all":
        counts = invalidate_all()
    elif req.tier == "sql":
        counts = {"sql_results": sql_cache.invalidate()}
    elif req.tier == "dashboard":
        counts = {"dashboards": dash_cache.invalidate()}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {req.tier}")

    log.info(f"[CACHE] Invalidated: {counts}")
    return {"status": "ok", "cleared": counts}


# ── Company endpoints ────────────────────────────────────────────

@router.get("/companies")
async def list_companies(user_id: str = "web_user"):
    """قائمة الشركات المتاحة للمستخدم."""
    companies = await get_user_companies(user_id)
    return {"companies": companies}
