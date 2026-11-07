"""
routers/chat.py — Main chat endpoint using the ERP Intelligence Pipeline.
"""
import re
import csv
import io
import logging
import traceback
from fastapi import APIRouter, HTTPException, Request
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
import rbac as _rbac

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


class TokenInfo(BaseModel):
    used_today:  int = 0
    budget:      int = 0
    remaining:   int = -1
    pct_used:    float = 0.0
    calls_today: int = 0
    unlimited:   bool = True
    role:        str = ""


class ChatResponse(BaseModel):
    answer: str
    sql_generated: str
    row_count: int
    method: str = ""
    template_used: str = ""
    execution_time_ms: int = 0
    chart_data: Optional[dict] = None
    widgets: Optional[list] = None
    suggestions: Optional[list] = None
    insights: Optional[list] = None
    proactive_alerts: Optional[list] = None
    health_scores: Optional[dict] = None
    action_card: Optional[dict] = None
    action_id: Optional[str] = None
    navigation_links: Optional[list] = None
    export_available: Optional[dict] = None
    report_data: Optional[dict] = None
    # ── New fields ──────────────────────────────────────────────────
    token_info: Optional[TokenInfo] = None       # per-user token budget
    reasoning_steps: Optional[list] = None       # pipeline thinking steps


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    try:
        # ── Identity resolution ────────────────────────────────────────
        # Priority: JWT-verified identity > body user_id.
        # When AUTH_MODE=jwt a missing/invalid token is a hard 401.
        # When AUTH_MODE=api_key the body user_id is accepted (legacy) —
        # in that mode access is gated by X-API-Key at the middleware level,
        # not per-user identity. Switch to AUTH_MODE=jwt for real RBAC.
        _auth_user = _rbac.authenticate_request(dict(request.headers))
        if _auth_user:
            # Verified identity from JWT — body user_id is ignored
            if _auth_user != req.user_id:
                log.warning(
                    "[AUTH] Body user_id=%r overridden by JWT-verified identity=%r",
                    req.user_id, _auth_user,
                )
            effective_user_id = _auth_user
        else:
            if _rbac._AUTH_MODE == "jwt":
                # JWT mode with no valid token → hard reject
                raise HTTPException(
                    status_code=401,
                    detail="المصادقة مطلوبة — يرجى إرسال Authorization: Bearer <token> صالح",
                )
            # api_key / dev mode: accept body claim (existing behaviour)
            effective_user_id = req.user_id

        history = [{"role": m.role, "content": m.content} for m in req.history]

        # ── Token budget check ─────────────────────────────────────
        perms_pre = _rbac.get_user_permissions(effective_user_id)
        budget = perms_pre.daily_token_budget
        _token_allowed = True
        try:
            from token_tracker import check_budget, get_usage_summary
            _token_allowed, _used, _remaining = check_budget(effective_user_id, budget)
        except Exception:
            pass

        if not _token_allowed:
            from token_tracker import get_usage_summary
            _summary = get_usage_summary(effective_user_id, budget)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"تجاوزت الحد اليومي المسموح ({budget:,} توكن). "
                    f"استخدمت اليوم: {_summary['used_today']:,} توكن. "
                    "يُعاد تفعيل الحصة عند منتصف الليل."
                ),
            )

        result = await process_question(
            question=req.question,
            user_id=effective_user_id,
            company_code=req.company_code,
            fiscal_year=req.fiscal_year,
            history=history,
        )

        # Inject proactive alerts on greeting/first message
        proactive_alerts = None
        if result.method in ("greeting", "help"):
            try:
                from proactive.alerts import alert_store as _astore
                unack = _astore.get_unacknowledged()
                if unack:
                    proactive_alerts = [a.to_dict() for a in unack[:5]]
            except Exception:
                pass

        # Audit log
        try:
            from audit_log import log_interaction
            log_interaction(
                user_id=effective_user_id,
                question=req.question,
                intent_category=result.intent.category if result.intent else "",
                intent_sub=result.intent.sub_intent if result.intent else "",
                intent_confidence=result.intent.confidence if result.intent else 0,
                method=result.method,
                template_used=result.template_used,
                sql_generated=result.sql,
                row_count=result.row_count,
                answer_preview=result.answer[:200],
                execution_time_ms=result.execution_time_ms,
                cache_hit="+cached" in result.method,
            )
        except Exception:
            pass

        # RBAC: filter response based on user role
        sql_for_response = result.sql
        export_for_response = result.export_available
        try:
            perms = _rbac.get_user_permissions(effective_user_id)
            if not perms.can_view_sql:
                sql_for_response = ""
            if not perms.can_export:
                export_for_response = None
        except Exception:
            pass

        # ── Token info for UI ──────────────────────────────────────
        token_info = None
        try:
            from token_tracker import get_usage_summary
            _summary = get_usage_summary(effective_user_id, budget)
            token_info = TokenInfo(
                used_today  = _summary["used_today"],
                budget      = _summary["budget"],
                remaining   = _summary["remaining"],
                pct_used    = _summary["pct_used"],
                calls_today = _summary["calls_today"],
                unlimited   = _summary["unlimited"],
                role        = perms_pre.role,
            )
        except Exception:
            pass

        return ChatResponse(
            answer=result.answer,
            sql_generated=sql_for_response,
            row_count=result.row_count,
            method=result.method,
            template_used=result.template_used,
            execution_time_ms=result.execution_time_ms,
            chart_data=result.chart_data,
            widgets=result.widgets,
            suggestions=result.suggestions or None,
            insights=result.insights or None,
            proactive_alerts=proactive_alerts,
            action_card=result.action_card,
            action_id=result.action_id,
            navigation_links=result.navigation_links,
            export_available=export_for_response,
            report_data=result.report_data,
            token_info=token_info,
            reasoning_steps=getattr(result, "reasoning_steps", None),
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


@router.get("/token-budget/{user_id}")
async def get_token_budget(user_id: str):
    """Return daily token budget and usage for a user."""
    try:
        from token_tracker import get_usage_summary
        perms = _rbac.get_user_permissions(user_id)
        summary = get_usage_summary(user_id, perms.daily_token_budget)
        summary["role"] = perms.role
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    tier: str = "all"  # all | sql | dashboard | response


@router.post("/cache/invalidate")
async def cache_invalidate(req: CacheInvalidateRequest):
    """إبطال الكاش — يمسح البيانات المخزنة مؤقتاً.
    tier=all      → sql + dashboard + response caches
    tier=sql      → SQL results only
    tier=dashboard → dashboard cache only
    tier=response → pipeline response cache (question→answer pairs, 5-min TTL)
    """
    if req.tier == "all":
        counts = invalidate_all()
        try:
            import response_cache as _rc
            counts["response"] = _rc.invalidate_all()
        except Exception:
            pass
    elif req.tier == "sql":
        counts = {"sql_results": sql_cache.invalidate()}
    elif req.tier == "dashboard":
        counts = {"dashboards": dash_cache.invalidate()}
    elif req.tier == "response":
        try:
            import response_cache as _rc
            counts = {"response": _rc.invalidate_all()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
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


# ── Schema debug / reload endpoints ─────────────────────────────

@router.get("/schema-debug")
async def schema_debug(question: str = ""):
    """Debug schema selection for a question.

    Returns which tables were selected (primary/referenced), their token-overlap
    scores, context length, comments file mtime, cache hit status, blocked tables,
    and a sample of the flag-concept map derived from comments.

    Example: GET /chat/schema-debug?question=أعلى 5 عملاء
    """
    from schema_loader import get_schema_debug_info
    from cache import schema_cache, make_schema_key

    # Check cache BEFORE calling get_schema_debug_info (which may populate it)
    cache_hit = False
    if question.strip():
        cache_hit = schema_cache.get(make_schema_key(question)) is not None

    info = get_schema_debug_info(question)
    return {**info, "cache_hit": cache_hit}


@router.post("/reload-schema")
async def reload_schema():
    """Force reload of justclick_comments.sql and clear all schema/response caches.

    Use this after editing justclick_comments.sql to apply changes immediately
    without waiting for the 5-minute cache TTL or the hot-reload mtime check.
    """
    from schema_loader import force_reload_schema
    result = force_reload_schema()
    log.info(f"[SCHEMA] force-reloaded via POST /chat/reload-schema: {result}")
    return {"status": "ok", **result}
