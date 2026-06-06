"""
pipeline.py — ERP Intelligence Router Pipeline
The central engine that orchestrates:
  Intent Classification -> Template Matching -> Safe SQL -> Execution -> Formatting
  + Action Engine -> Workflow -> Export -> APEX Navigation -> Executive Reports
"""
import re
import os
import logging
import sys
import time

log = logging.getLogger("pipeline")
# Use UTF-8 stream handler to support Arabic on Windows
_handler = logging.StreamHandler(stream=open(sys.stderr.fileno(), mode='w', encoding='utf-8', closefd=False))
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
from dataclasses import dataclass, field
from typing import Optional

from intent_classifier import classify_intent, Intent
from query_templates import find_template, render_template, QueryTemplate
from sql_safety import validate_sql, log_query, SafetyResult
from memory import (
    get_session, add_user_turn, add_assistant_turn,
    get_history_messages, get_context_entities,
)
from schema_loader import get_relevant_schema
from llm_client import generate_sql, format_answer, _call_llm
from db import execute_query
from dashboard_engine import find_dashboard_by_query, execute_dashboard
from cache import (
    sql_cache, dash_cache, schema_cache,
    make_sql_key, make_dash_key, make_schema_key,
)
from company_manager import inject_company_filter, validate_company_access
from copilot import (
    generate_suggestions, generate_insights, auto_generate_chart,
    COPILOT_GREETING, COPILOT_HELP, GREETING_SUGGESTIONS,
)

# ERP Operator imports
from erp_actions.planner import detect_action_intent, is_confirmation, is_rejection, plan_action
from erp_actions.executor import confirm_and_execute, reject_action
from erp_actions.store import get_user_pending, save_action
from erp_actions.workflows import is_workflow_query, get_pending_approvals, get_request_status, get_approval_summary
from erp_actions.apex_nav import detect_navigation_intent, find_pages
from export_engine import detect_export_intent, ExportRequest, generate_export, ExportFormat
from executive_reports import detect_report_intent, generate_executive_report, format_report_for_chat


# ── Hybrid semantic-first routing gate ───────────────────────────────
# Meaning decides whether a fast template MAY be used; the template is only an
# execution optimization, never the source of meaning. This gate can only DEMOTE
# template→LLM (never fabricate SQL), so the worst case is a slower-but-correct
# LLM answer — a safe failure mode. Set SEMANTIC_FIRST=0 to revert to pure
# template-first routing. It deliberately uses only CHEAP, RELIABLE signals
# (intent entities + transaction-type words + the template's own SQL) and NOT the
# reasoning plan, whose dimension/table/time detection over-fires (verified).
_GATE_SPECIFIC_ENTITIES = (
    "customer_name", "store_name", "employee_name", "supplier_name", "item_name",
)
_GATE_TIME_WORDS = (
    "اليوم", "النهارده", "today", "امس", "أمس", "الشهر", "السنة", "سنة",
    "الربع", "اسبوع", "أسبوع", "week", "month", "year",
)


def _template_filter_values(sql_upper: str) -> dict:
    """Parse coded filter values from template SQL — handles both literal digits
    (COLUMN = 1) and comment-first placeholders ({{flag:COLUMN:label}}).

    After Phase-C migration no template contains bare digits in filter conditions;
    they all use {{flag:…}} placeholders.  Without this function resolving those
    placeholders the semantic gate's transaction-type check (#3) is permanently
    blind, so misrouted queries (e.g. a 'مشتريات' question reaching an INVTYPE=بيع
    template) cannot be caught.  Resolving at gate-time keeps the single source of
    truth (comments) while restoring the safety net.
    """
    result: dict[str, str] = {}
    # 1. Legacy literal digits
    for m in re.finditer(r'\b([A-Z_][A-Z0-9_]*)\s*=\s*(\d+)\b', sql_upper):
        result[m.group(1)] = m.group(2)
    # 2. Comment-first flag placeholders: {{flag:COLUMN:label}} (uppercase after .upper())
    for m in re.finditer(r'\{\{FLAG:([A-Z_][A-Z0-9_]*):([^}]+)\}\}', sql_upper):
        col, label = m.group(1), m.group(2).strip()
        try:
            from schema_loader import resolve_flag
            val = resolve_flag(col, label)
            if val is not None:
                result[col] = str(val)
        except Exception:
            pass
    return result


def _question_txn(question: str):
    """Return an explicit INVTYPE value (0=sales,1=purchase) ONLY if the question
    itself names a sales/purchase concept — resolved via the comment flag-dictionary
    (get_flag_concept_map), NOT a hardcoded keyword list. None if absent or ambiguous
    (both concepts present), so an ambiguous query never guesses.
    """
    try:
        from schema_loader import get_flag_concept_map, _normalize_concept
        qn = _normalize_concept(question or "")
        found = set()
        for label, mappings in get_flag_concept_map().items():
            if label in qn:
                for col, val in mappings:
                    if col == "INVTYPE":
                        found.add(val)
        if len(found) == 1:
            return int(found.pop())
    except Exception:
        pass
    return None


# Cache of normalized comment words, keyed by comments mtime (rebuilt on edit).
_comment_words: set[str] = set()
_comment_words_mtime: float = -1.0


def _get_comment_words() -> set[str]:
    """Normalized word set drawn ONLY from schema comment text (table + column),
    mtime-cached so comment edits are picked up without a restart. No keyword tables,
    no synonyms — comment vocabulary is the authority."""
    global _comment_words, _comment_words_mtime
    import schema_loader
    from schema_loader import _normalize_concept, _maybe_reload_comments
    _maybe_reload_comments()
    if schema_loader._comments_mtime != _comment_words_mtime or not _comment_words:
        words: set[str] = set()
        def _add(text: str) -> None:
            for w in re.findall(r'[؀-ۿA-Za-z]+', text or ''):
                n = _normalize_concept(w)
                if len(n) >= 3:
                    words.add(n)
        for desc in schema_loader._table_comments.values():
            _add(desc)
        for cols in schema_loader._column_comments.values():
            for desc in cols.values():
                _add(desc)
        _comment_words = words
        _comment_words_mtime = schema_loader._comments_mtime
    return _comment_words


def _question_has_comment_word(question: str) -> bool:
    """True if any token of the question appears in the schema COMMENTS, after Arabic
    normalization. Fail-open: on any internal error returns True so a real question is
    never wrongly blocked."""
    try:
        from schema_loader import _normalize_concept
        cw = _get_comment_words()
        for w in re.findall(r'[؀-ۿA-Za-z]+', question or ''):
            if _normalize_concept(w) in cw:
                return True
        return False
    except Exception:
        return True


def _foreign_comment_nouns(question: str) -> list[str]:
    """Return the ال-prefixed NOUN subjects in the question whose normalized root is
    NOT in the schema comments (nor an existing time word).

    These are words the user is asking ABOUT that the comments do not define. A fast
    template can match on a PARTIAL phrase (regex) and silently drop such a qualifier
    — e.g. "عدد فواتير الطقس" matches "عدد فواتير" → sales-count template, ignoring
    "الطقس" and returning a WRONG count. Detecting a foreign comment-noun lets the
    caller return not-found instead of a wrong answer.

    Scope is deliberately narrow to avoid false positives:
      • only ال-prefixed tokens (noun subjects) — request verbs like عايز/اعرض/هات
        carry no ال and are never flagged;
      • known = comment vocabulary ∪ the EXISTING _GATE_TIME_WORDS (reused, not a new
        list) so colloquial time words (النهارده) are not flagged.
    Fail-open to [] so an internal error never blocks a real query.
    """
    try:
        from schema_loader import _normalize_concept
        known = set(_get_comment_words())
        for w in _GATE_TIME_WORDS:
            n = _normalize_concept(w)
            if len(n) >= 3:
                known.add(n)
        out: list[str] = []
        for w in re.findall(r'[؀-ۿ]+', question or ''):
            if not (w.startswith('ال') and len(w) > 4):
                continue
            n = _normalize_concept(w)   # strips leading ال
            if len(n) >= 3 and n not in known:
                out.append(w)
        return out
    except Exception:
        return []


def _template_matches_meaning(template, entities: dict, question: str) -> tuple[bool, str]:
    """Is this fast template consistent with the question's MEANING?
    Returns (consistent, reason_if_not). False ⇒ skip template, use the LLM path.

    The authority for business meaning is the schema comments + ontology. The
    transaction-type check below derives its concepts from the comment flag-
    dictionaries (single source of truth), NOT from hardcoded keyword lists; the
    reasoning engine is intentionally not consulted as a routing authority. Time
    and entity checks are question-intent signals that the comments support.
    """
    sql_u = (getattr(template, "sql", "") or "").upper()
    q = question or ""
    entities = entities or {}

    # 1. Time scope — template must not impose a date filter the user didn't ask for
    if "SYSDATE" in sql_u:
        wants_time = ("time_today" in entities) or any(w in q for w in _GATE_TIME_WORDS)
        if not wants_time:
            return False, "template imposes a date filter the question didn't request"

    # 2. Specific entity — template cannot honor a named customer/store/item/etc.
    present = [k for k in _GATE_SPECIFIC_ENTITIES if k in entities]
    if present:
        consumed = set(template.required_params) | set(template.optional_params)
        if not any(k in consumed for k in present):
            return False, f"question names {present} but the template can't filter by it"

    # 3. Transaction type — COMMENT-DERIVED. If the question names a coded concept
    #    whose comment-defined value conflicts with a value the template hard-codes
    #    (comment: 'INVTYPE 0=بيع 1=شراء' → a شراء question must not use an
    #    INVTYPE=0 template). Concepts come from the comments, so this auto-extends.
    try:
        from schema_loader import get_flag_concept_map, _normalize_concept
        q_norm = _normalize_concept(q)
        tmpl_filters = _template_filter_values(sql_u)
        if tmpl_filters:
            for label, mappings in get_flag_concept_map().items():
                if label in q_norm:
                    for col, val in mappings:
                        if col in tmpl_filters and tmpl_filters[col] != val:
                            return False, (f"comments map '{label}' → {col}={val}, "
                                           f"but template forces {col}={tmpl_filters[col]}")
    except Exception:
        pass

    return True, ""


def _record_viz(domain: str, sub_intent: str, data: list, chart: dict) -> None:
    """Non-blocking: record chart selection into AI_VIZ_RULES for adaptive learning."""
    try:
        from learning.visualization import record_chart_selection, analyze_data_shape
        data_shape = analyze_data_shape(data, sub_intent)
        record_chart_selection(domain, sub_intent, data_shape, chart.get("type", "bar"))
    except Exception:
        pass


@dataclass
class PipelineResult:
    answer: str
    sql: str = ""
    row_count: int = 0
    intent: Optional[Intent] = None
    template_used: str = ""
    method: str = ""           # template | llm_controlled | greeting | help | error | dashboard | action | workflow | export | navigation | report
    error: str = ""            # exception text when method == "error" (recorded to AI_EVENTS)
    execution_time_ms: int = 0
    safety_warnings: list[str] = field(default_factory=list)
    chart_data: Optional[dict] = None   # {type, labels, datasets} for Chart.js
    widgets: Optional[list] = None      # multi-widget response (KPIs + charts + tables in chat)
    suggestions: list = field(default_factory=list)   # copilot follow-up suggestions
    insights: list = field(default_factory=list)      # copilot business insights
    # ERP Operator fields
    action_card: Optional[dict] = None        # Action confirmation card
    action_id: Optional[str] = None           # Pending action ID
    navigation_links: Optional[list] = None   # APEX page links
    export_available: Optional[dict] = None   # Export metadata
    report_data: Optional[dict] = None        # Executive report data


# ── Greeting responses ────────────────────────────────────────────
_GREETING_RESPONSES = [COPILOT_GREETING]

_HELP_RESPONSE = COPILOT_HELP

# ── Intent-to-label mapping for Phase 7 predictions ─────────────
_INTENT_LABELS = {
    "sales_today": "مبيعات اليوم",
    "sales_summary": "ملخص المبيعات",
    "purchase_summary": "ملخص المشتريات",
    "top_customers": "أعلى العملاء",
    "top_items": "أعلى الأصناف مبيعاً",
    "stock_balance": "رصيد المخزون",
    "account_balance": "رصيد الحساب",
    "account_statement": "كشف حساب",
    "customer_balance": "رصيد العميل",
    "outstanding": "المديونيات",
    "employee_count": "عدد الموظفين",
    "trial_balance": "ميزان المراجعة",
    "revenue_expenses": "الإيرادات والمصروفات",
    "item_info": "بيانات الأصناف",
    "invoice_detail": "تفاصيل الفاتورة",
    "salary_info": "الرواتب",
    "attendance": "الحضور والانصراف",
}

_INTENT_QUERIES = {
    "sales_today": "إجمالي المبيعات اليوم",
    "sales_summary": "ملخص المبيعات هذا الشهر",
    "purchase_summary": "إجمالي المشتريات هذا الشهر",
    "top_customers": "أعلى 5 عملاء في المبيعات",
    "top_items": "أعلى 10 أصناف مبيعاً",
    "stock_balance": "رصيد المخازن",
    "account_balance": "أرصدة الحسابات الرئيسية",
    "account_statement": "كشف حساب",
    "customer_balance": "أرصدة العملاء المستحقة",
    "outstanding": "المديونيات المتأخرة",
    "employee_count": "كم عدد الموظفين",
    "trial_balance": "ميزان المراجعة",
    "revenue_expenses": "الإيرادات والمصروفات خلال آخر 3 شهور",
    "item_info": "اعرض الأصناف",
    "invoice_detail": "آخر 10 فواتير",
    "salary_info": "رواتب الموظفين",
    "attendance": "الحضور والانصراف اليوم",
}


def _intent_to_label(intent_name: str) -> str:
    """Convert intent name to Arabic label for suggestion chips."""
    return _INTENT_LABELS.get(intent_name, intent_name.replace("_", " "))


def _intent_to_query(intent_name: str) -> str:
    """Convert intent name to a clickable query string."""
    return _INTENT_QUERIES.get(intent_name, _intent_to_label(intent_name))


# ══════════════════════════════════════════════════════════════════
# Main Pipeline
# ══════════════════════════════════════════════════════════════════

async def process_question(
    question: str,
    user_id: str = "anonymous",
    company_code: str = "1",
    fiscal_year: str = "2024",
    history: list = None,
) -> PipelineResult:
    """
    Main entry point. Routes question through the intelligence pipeline.
    """
    start = time.time()
    question = question.strip()
    if not question:
        return PipelineResult(answer="يرجى كتابة سؤال.", method="error")

    # ── Prompt injection detection ──
    from sql_safety import detect_prompt_injection
    injection = detect_prompt_injection(question)
    if injection:
        log.warning(f"[PIPELINE] Prompt injection detected from user={user_id}")
        return PipelineResult(
            answer="عذراً، لا يمكن معالجة هذا الطلب.",
            method="error",
            safety_warnings=["prompt_injection_detected"],
        )

    # ── RBAC: Domain access check (after intent detection, applied later) ──
    # Pre-load user permissions for row-limit and export enforcement
    try:
        from rbac import get_user_permissions, get_max_rows
        _user_perms = get_user_permissions(user_id)
    except Exception:
        _user_perms = None

    # ── Response cache check (skip for action/workflow questions) ──
    try:
        import response_cache
        cached = response_cache.get(question, company_code, fiscal_year)
        if cached:
            return PipelineResult(
                answer=cached.answer,
                sql=cached.sql,
                row_count=cached.row_count,
                method=f"{cached.method}+cached",
                template_used=cached.template_used,
                chart_data=cached.chart_data,
                suggestions=cached.suggestions,
                insights=cached.insights,
                execution_time_ms=1,
            )
    except Exception:
        pass

    # ── Step 0: Company access validation ──
    if company_code:
        has_access = await validate_company_access(user_id, company_code)
        if not has_access:
            return PipelineResult(
                answer="ليس لديك صلاحية على هذه الشركة.",
                method="error",
            )

    # ══════════════════════════════════════════════════════════════
    # ERP OPERATOR LAYER (pre-classification fast-path)
    # Handles: confirmations, rejections, actions, workflows,
    #          exports, navigation, executive reports
    # ══════════════════════════════════════════════════════════════

    # ── Operator: Confirmation/Rejection of pending action ──
    pending_action = get_user_pending(user_id)
    if pending_action:
        if is_confirmation(question):
            log.info(f"[PIPELINE] User confirmed action {pending_action.id}")
            executed = await confirm_and_execute(pending_action.id, user_id)
            if executed:
                return PipelineResult(
                    answer=executed.result_message or "✅ تم تنفيذ الإجراء بنجاح.",
                    method="action",
                    action_card=executed.result_card(),
                    action_id=executed.id,
                    execution_time_ms=int((time.time() - start) * 1000),
                )
            else:
                return PipelineResult(
                    answer="❌ فشل تنفيذ الإجراء. يرجى المحاولة مرة أخرى.",
                    method="action",
                    action_id=pending_action.id,
                    execution_time_ms=int((time.time() - start) * 1000),
                )
        elif is_rejection(question):
            log.info(f"[PIPELINE] User rejected action {pending_action.id}")
            await reject_action(pending_action.id, user_id, "رفض المستخدم")
            return PipelineResult(
                answer="تم إلغاء الإجراء.",
                method="action",
                action_id=pending_action.id,
                execution_time_ms=int((time.time() - start) * 1000),
            )

    # ── Operator: Action Intent Detection ──
    action_intent = detect_action_intent(question)
    if action_intent:
        action_type, params = action_intent
        log.info(f"[PIPELINE] Action detected: {action_type} params={params}")
        try:
            plan = plan_action(
                action_type=action_type,
                params=params,
                user_id=user_id,
                company_code=company_code,
                fiscal_year=fiscal_year,
            )
            if plan:
                save_action(plan)
                card = plan.confirmation_card()
                return PipelineResult(
                    answer=card.get("message", "هل تريد تنفيذ هذا الإجراء؟"),
                    method="action",
                    action_card=card,
                    action_id=plan.id,
                    execution_time_ms=int((time.time() - start) * 1000),
                    suggestions=[
                        {"label": "نعم، نفّذ", "query": "نعم", "icon": "new", "source": "workflow"},
                        {"label": "لا، إلغاء", "query": "لا", "icon": "alert", "source": "workflow"},
                    ],
                )
        except Exception as e:
            log.warning(f"[PIPELINE] Action planning failed: {e}")
            # Fall through to standard pipeline — don't silently fail

    # ── Operator: Workflow Queries ──
    workflow_type = is_workflow_query(question)
    if workflow_type:
        log.info(f"[PIPELINE] Workflow query: {workflow_type}")
        result = await _handle_workflow_query(
            workflow_type=workflow_type,
            user_id=user_id,
            company_code=company_code,
        )
        if result:
            result.execution_time_ms = int((time.time() - start) * 1000)
            add_user_turn(user_id, question, {}, "workflow")
            add_assistant_turn(user_id, result.answer, "", 0, {})
            return result

    # ── Operator: Executive Report Detection ──
    report_type = detect_report_intent(question)
    if report_type:
        log.info(f"[PIPELINE] Executive report: {report_type}")
        result = await _handle_executive_report(
            report_type=report_type,
            company_code=company_code,
            fiscal_year=fiscal_year,
        )
        if result:
            result.execution_time_ms = int((time.time() - start) * 1000)
            add_user_turn(user_id, question, {}, "report")
            add_assistant_turn(user_id, result.answer, "", 0, {})
            return result

    # ── Operator: Export Detection ──
    export_format = detect_export_intent(question)
    if export_format:
        log.info(f"[PIPELINE] Export detected: {export_format}")
        # Export needs data context — set flag for post-processing
        # The actual export will be triggered from the frontend when data is available

    # ── Operator: APEX Navigation Detection ──
    nav_pages = detect_navigation_intent(question)
    if nav_pages:
        log.info(f"[PIPELINE] Navigation: {len(nav_pages)} pages matched")
        result = _handle_navigation(nav_pages)
        if result:
            result.execution_time_ms = int((time.time() - start) * 1000)
            add_user_turn(user_id, question, {}, "navigation")
            add_assistant_turn(user_id, result.answer, "", 0, {})
            return result

    # ══════════════════════════════════════════════════════════════
    # STANDARD PIPELINE (analysis path)
    # ══════════════════════════════════════════════════════════════

    # ── Step 1: Get conversation context ──
    session_history = get_history_messages(user_id)
    context_entities = get_context_entities(user_id)

    # ── Step 1.5: Check if this is a follow-up (Conversational BI) ──
    followup_context_str = ""
    try:
        from learning.engine import check_followup
        followup_info = check_followup(question, user_id)
        if followup_info and followup_info.get("is_followup"):
            from learning.conversation_bi import build_followup_context
            followup_context_str = build_followup_context(user_id)
            log.info(f"[PIPELINE] Follow-up detected: modifier={followup_info.get('modifier')}")
    except Exception as e:
        log.debug(f"[PIPELINE] Follow-up check skipped: {e}")

    # ── Step 2: Classify intent ──
    intent = classify_intent(question, session_history)
    log.info(f"[PIPELINE] intent={intent.category} domain={intent.domain} "
             f"sub={intent.sub_intent} entities_keys={list(intent.entities.keys())}")

    # ── Step 2.5: Enhance intent via Learning Engine ──
    if intent.confidence < 0.90 and intent.category not in ("greeting", "help"):
        try:
            from learning.engine import enhance_intent
            enhanced_sub, enhanced_conf = enhance_intent(
                question, intent.sub_intent, intent.confidence
            )
            if enhanced_conf > intent.confidence:
                log.info(f"[PIPELINE] Intent enhanced: {intent.sub_intent}->{enhanced_sub} "
                         f"conf={intent.confidence:.2f}->{enhanced_conf:.2f}")
                intent.sub_intent = enhanced_sub
                intent.confidence = enhanced_conf
        except Exception as e:
            log.debug(f"[PIPELINE] enhance_intent skipped: {e}")

    # Merge context entities with newly extracted ones
    merged_entities = {**context_entities, **intent.entities}
    intent.entities = merged_entities

    # Record user turn
    add_user_turn(user_id, question, intent.entities, intent.sub_intent)

    # ── Step 3: Route by intent category ──
    result: PipelineResult

    if intent.category == "greeting":
        greeting_text = _GREETING_RESPONSES[0]
        # Inject proactive operational summary into greeting
        try:
            from proactive.alerts import alert_store as _pstore
            unack = _pstore.get_unacknowledged()
            if unack:
                critical = [a for a in unack if a.severity == "critical"]
                warnings = [a for a in unack if a.severity == "warning"]
                parts = []
                if critical:
                    parts.append(f"{len(critical)} تنبيه حرج")
                if warnings:
                    parts.append(f"{len(warnings)} تحذير")
                if parts:
                    alert_line = " و ".join(parts)
                    greeting_text += f"\n\n⚡ **لديك {alert_line} يحتاج اهتمامك** — اطلع على التنبيهات من أيقونة الجرس."
        except Exception:
            pass

        result = PipelineResult(
            answer=greeting_text,
            intent=intent,
            method="greeting",
            suggestions=GREETING_SUGGESTIONS[:4],
        )

    elif intent.category == "help":
        result = PipelineResult(
            answer=_HELP_RESPONSE,
            intent=intent,
            method="help",
            suggestions=GREETING_SUGGESTIONS[:4],
        )

    elif _wants_dashboard(question):
        log.debug(f"[PIPELINE] Dashboard matched for: {question}")
        result = await _handle_dashboard(question, session_history)
        if not result:
            log.info("[PIPELINE] Dashboard detected but no match -> LLM data query path")
            result = await _handle_data_query(
                question=question,
                intent=intent,
                user_id=user_id,
                company_code=company_code,
                fiscal_year=fiscal_year,
                history=history or session_history,
                followup_context=followup_context_str,
            )

    else:
        log.debug(f"[PIPELINE] Data query path for: {question}")
        result = await _handle_data_query(
            question=question,
            intent=intent,
            user_id=user_id,
            company_code=company_code,
            fiscal_year=fiscal_year,
            history=history or session_history,
            followup_context=followup_context_str,
        )

    # Record assistant turn
    add_assistant_turn(
        user_id, result.answer, result.sql, result.row_count, intent.entities
    )

    result.execution_time_ms = int((time.time() - start) * 1000)

    # ── Export availability flag ──
    # If export was detected earlier but data came from a query, flag it
    if export_format and result.row_count > 0:
        result.export_available = {
            "format": export_format,
            "row_count": result.row_count,
            "message": f"يمكن تصدير النتائج ({result.row_count} سجل) بصيغة {export_format.upper()}",
        }

    # ── Learning Engine hook (Phase 6: pass session_id) ──
    try:
        from learning.engine import on_query_complete
        on_query_complete(
            question=question,
            sub_intent=intent.sub_intent,
            domain=intent.domain,
            template_used=result.template_used,
            sql=result.sql,
            row_count=result.row_count,
            exec_ms=result.execution_time_ms,
            success=result.method not in ("error",),
            user_id=user_id,
            method=result.method,
            session_id=user_id,
            error=getattr(result, "error", ""),
        )
    except Exception as e:
        log.warning(f"[LEARNING] on_query_complete failed: {e}")

    # ── Phase 7: Predict next intent — merge with existing suggestions ──
    if result.method not in ("error", "greeting", "help") and intent.sub_intent:
        try:
            from learning.analytics_tracker import predict_next_intent
            session = get_session(user_id)
            recent_intents = [t.intent for t in session.turns[-6:] if t.intent]
            if recent_intents:
                predictions = predict_next_intent(recent_intents, top_k=3)
                if predictions:
                    # Convert predictions to unified suggestion format
                    predicted_suggestions = []
                    for p in predictions[:3]:
                        intent_name = p["intent"]
                        predicted_suggestions.append({
                            "label": _intent_to_label(intent_name),
                            "query": _intent_to_query(intent_name),
                            "icon": "predict",
                            "source": "prediction",
                        })
                    existing = result.suggestions or []
                    # Tag existing suggestions with source if not tagged
                    for s in existing:
                        if isinstance(s, dict) and "source" not in s:
                            s["source"] = "copilot"
                    # Merge: existing first, then predicted (deduplicated by query)
                    seen_queries = set()
                    merged = []
                    for s in existing + predicted_suggestions:
                        if isinstance(s, dict):
                            q = s.get("query", "")
                        else:
                            q = str(s)
                            s = {"label": q, "query": q, "icon": "suggest", "source": "copilot"}
                        if q and q not in seen_queries:
                            seen_queries.add(q)
                            merged.append(s)
                    result.suggestions = merged[:6]
        except Exception:
            pass

    # ── Store in response cache (for repeated questions) ──
    if result.method not in ("error", "greeting", "help", "action"):
        try:
            import response_cache
            response_cache.put(
                question=question,
                company_code=company_code,
                fiscal_year=fiscal_year,
                answer=result.answer,
                sql=result.sql,
                row_count=result.row_count,
                method=result.method,
                chart_data=result.chart_data,
                suggestions=result.suggestions,
                insights=result.insights,
                template_used=result.template_used,
            )
        except Exception:
            pass

    return result


async def _handle_data_query(
    question: str,
    intent: Intent,
    user_id: str,
    company_code: str,
    fiscal_year: str,
    history: list,
    followup_context: str = "",
) -> PipelineResult:
    """Handle data query: template match first, then LLM fallback."""

    # ── FIX 2/3/4: resolve INVTYPE for ambiguous INVID lookups (sales vs purchase) ──
    # INVID is NOT unique across invoice types (per MAIN_INV.INVID comment), so an
    # invoice-detail lookup MUST be scoped by INVTYPE. Priority: explicit in the
    # question → inherited from session txn_context → otherwise leave UNSET so the
    # template's required 'invtype' param is missing → find_template returns None →
    # LLM fallback (never execute a leaky template). No guessing.
    if os.getenv("CONTEXT_ENFORCE", "1") != "0" \
            and intent.sub_intent == "invoice_detail" \
            and "invtype" not in intent.entities:
        _txn = _question_txn(question)
        if _txn is None:
            try:
                from learning.conversation_bi import get_context as _bi_get
                _txn = (_bi_get(user_id).get("txn_context") or {}).get("INVTYPE")
            except Exception:
                _txn = None
        if _txn is not None:
            intent.entities["invtype"] = str(_txn)
            log.info(f"[PIPELINE] invoice_detail scoped to INVTYPE={_txn} "
                     f"(source={'question' if _question_txn(question) is not None else 'session'})")
        else:
            log.info("[PIPELINE] invoice_detail with unknown INVTYPE -> LLM (fail-safe)")

    # ── Try template matching ──
    if intent.sub_intent:
        # If question is contextual (LLM-classified, no entities, has history)
        # skip template and go to LLM-controlled which uses conversation history
        if _needs_history_context(intent, history):
            log.info(f"[PIPELINE] Contextual question (confidence={intent.confidence:.2f}), "
                     f"skipping template -> LLM with history")
        else:
            template = find_template(intent.sub_intent, intent.entities)
            log.info(f"[PIPELINE] sub_intent={intent.sub_intent} template={'FOUND:'+template.name if template else 'NONE'}")

            # Hybrid semantic-first gate: the derived MEANING must agree with the
            # template before it may short-circuit the LLM. Otherwise → LLM path.
            if template and os.getenv("SEMANTIC_FIRST", "1") != "0":
                consistent, why = _template_matches_meaning(
                    template, intent.entities, question
                )
                if not consistent:
                    log.info(f"[PIPELINE] Semantic gate rejected template "
                             f"{template.name}: {why} -> LLM path")
                    template = None

            # Phase 2: Check template trust score from learning engine
            if template:
                try:
                    from learning.engine import should_use_template
                    if not should_use_template(template.name):
                        log.info(f"[PIPELINE] Template {template.name} low trust score -> LLM fallback")
                        template = None
                except Exception:
                    pass

            if template:
                result = await _execute_template(
                    template=template,
                    entities=intent.entities,
                    question=question,
                    user_id=user_id,
                    history=history,
                    company_code=company_code,
                    fiscal_year=fiscal_year,
                )
                log.info(f"[PIPELINE] template_result={'OK' if result else 'FAILED->LLM fallback'}")
                if result:
                    # Q5 fix: a fast template can match on a PARTIAL phrase (regex) and
                    # silently ignore an unknown qualifier the user asked about
                    # (e.g. "عدد فواتير الطقس" → sales-count, dropping "الطقس"). If the
                    # question names an ال-prefixed noun subject absent from the comments,
                    # the template answer is for the WRONG question → return not-found.
                    _foreign = _foreign_comment_nouns(question)
                    if _foreign:
                        is_arabic = any('؀' <= c <= 'ۿ' for c in question)
                        msg = ("لم أجد تعريفاً لهذا في تعليقات قاعدة البيانات" if is_arabic
                               else "Term not found in database comments.")
                        log.info(f"[PIPELINE] template {template.name} matched but question "
                                 f"has foreign comment-noun(s) {_foreign} -> not-found")
                        return PipelineResult(answer=msg, method="error", intent=intent)
                    result.intent = intent
                    return result
    else:
        log.info("[PIPELINE] no sub_intent, going to LLM")

    # ── CHANGE 2: gate the no-template fallback on COMMENT vocabulary ──
    # No usable template was produced. Before handing the question to the LLM,
    # require that it shares at least one word with the schema comments. If it
    # does not (and it is not a contextual follow-up that relies on prior turns),
    # there is no comment-grounded basis to answer → return a clear message
    # instead of letting the LLM answer from outside the comments.
    if not _needs_history_context(intent, history) \
            and not _question_has_comment_word(question):
        is_arabic = any('؀' <= c <= 'ۿ' for c in question)
        msg = ("لم أجد تعريفاً لهذا في تعليقات قاعدة البيانات" if is_arabic
               else "Term not found in database comments.")
        log.info("[PIPELINE] no comment-vocabulary match -> not-found message (no LLM)")
        return PipelineResult(answer=msg, method="error", intent=intent)

    # ── Fallback: controlled LLM SQL generation (comments only) ──
    result = await _execute_llm_controlled(
        question=question,
        intent=intent,
        user_id=user_id,
        company_code=company_code,
        fiscal_year=fiscal_year,
        history=history,
        followup_context=followup_context,
    )
    result.intent = intent
    return result


async def _execute_template(
    template: QueryTemplate,
    entities: dict,
    question: str,
    user_id: str,
    history: list,
    company_code: str = "",
    fiscal_year: str = "",
) -> Optional[PipelineResult]:
    """Execute a query template with extracted parameters.

    NOTE (F5 — known, by-design limitation): the SQL here is produced by
    render_template() from a vetted, fixed pattern. It deliberately does NOT
    consume learned knowledge / ontology / trained reports — those only shape
    the LLM path. The template path's two learning hooks are:
      1. should_use_template() (engine.py) — can demote a poorly-performing
         template to the LLM path where full knowledge IS injected;
      2. _comment_context_for_sql() (RC5) — grounds the ANSWER narrative in
         column business meaning.
    So template SQL stays stable/correct but cannot self-improve from training.
    To let a trained report override a template, route via should_use_template.
    """
    try:
        # Check required params
        missing = [p for p in template.required_params
                   if p not in entities and p not in template.param_defaults]
        if missing:
            log.info(f"[PIPELINE] Template {template.name} missing params: {missing}")
            return None

        # Render SQL from template
        sql = render_template(template, entities)

        log.info(f"[PIPELINE] Template={template.name} SQL={sql[:80]}...")

        # Safety check
        safety = validate_sql(sql)
        if not safety.is_safe:
            log.info(f"[PIPELINE] Template SQL blocked: {safety.blocked_reason}")
            log_query(user_id, question, sql, safety, success=False)
            return None

        sql = safety.sql

        # Execute
        data, err = await _try_execute(sql)

        if err:
            log.info(f"[PIPELINE] Template execution failed: {err[:150]}")
            log_query(user_id, question, sql, safety, success=False, error=err)
            return None  # Fall back to LLM

        # Auto-retry LIKE for account codes
        if len(data) == 0 and "account_code" in entities:
            data, sql = await _try_like_fallback(sql, entities.get("account_code", ""))

        # Auto-retry LIKE for name columns when exact match returns 0
        if len(data) == 0:
            data, sql = await _try_name_like_fallback(sql)

        truncated = any(row.get("__truncated__") for row in data)
        data = [row for row in data if not row.get("__truncated__")]

        # Format answer
        answer = _safe_format_answer(
            question=question,
            data=data,
            sql=sql,
            history=history,
            truncated=truncated,
        )

        if truncated:
            answer += "\n\n---\n⚠️ النتائج مقتصرة على أول 500 سجل — يمكن تضييق نطاق البحث للحصول على نتائج أكثر دقة."

        log_query(user_id, question, sql, safety, success=True, rows=len(data))

        # Build chart: explicit request or auto-generate
        chart = None
        if _wants_chart(question):
            chart = _build_chart_data(data, question)
        elif len(data) >= 2:
            chart = auto_generate_chart(data, question, getattr(template, 'domain', ""))

        # Copilot enrichment
        _domain = getattr(template, 'domain', "")
        _sub_intent = getattr(template, 'sub_intent', template.name)
        if chart:
            _record_viz(_domain, _sub_intent, data, chart)
        suggestions = generate_suggestions(
            question=question,
            sub_intent=_sub_intent,
            domain=_domain,
            data=data,
            entities=entities,
            row_count=len(data),
            has_chart=chart is not None,
        )
        insights = generate_insights(
            data=data,
            question=question,
            domain=_domain,
            row_count=len(data),
        )

        return PipelineResult(
            answer=answer,
            sql=sql,
            row_count=len(data),
            template_used=template.name,
            method="template",
            safety_warnings=safety.warnings,
            chart_data=chart,
            suggestions=suggestions,
            insights=insights,
        )

    except Exception as e:
        log.info(f"[PIPELINE] Template error: {e}")
        return None


async def _execute_llm_controlled(
    question: str,
    intent: Intent,
    user_id: str,
    company_code: str,
    fiscal_year: str,
    history: list,
    followup_context: str = "",
) -> PipelineResult:
    """Controlled LLM SQL generation with safety checks."""
    try:
        # Schema context with caching
        s_key = make_schema_key(question)
        schema_ctx = schema_cache.get(s_key)
        if schema_ctx is None:
            schema_ctx = get_relevant_schema(question)
            schema_cache.set(s_key, schema_ctx)
        else:
            log.info("[PIPELINE] Schema context cache HIT")

        # CHANGE 3: reasoning.decompose_query injection REMOVED. The rule engine no
        # longer feeds the LLM. Coded-value/metric/filter meaning must come from the
        # schema comments injected via schema_ctx — not from learning/reasoning.py.

        # FOLLOW-UP (Phase 3): get_llm_context injection REMOVED. The learning-engine
        # knowledge base + approved SQL examples are a non-comment meaning source
        # (its seed facts duplicate coded-value meaning, e.g. 'INVTYPE: 0=بيع'), so it
        # no longer feeds the LLM. Column/value meaning comes only from schema_ctx.

        # FOLLOW-UP (Phase 4): get_join_hint (ontology) injection REMOVED. JOIN
        # relationships are described in the comments themselves (FK markers / ⚠ JOIN
        # notes) and reach the LLM via schema_ctx — the learned ontology layer is a
        # non-comment source, so it no longer feeds the LLM.

        # Build extra context string
        extra_context = ""
        if followup_context:
            extra_context += f"\n{followup_context}\n"

        # FOLLOW-UP (Phase 5): trained-report semantic injection REMOVED.
        # search_knowledge_smart returns a learned/trained layer (AI_ERP_KNOWLEDGE)
        # carrying reference SQL with literal coded values, KPIs and entity flows —
        # all non-comment meaning. It no longer feeds the LLM; the LLM receives only
        # schema comments (schema_ctx) + the user question (+ followup_context).

        sql_raw = generate_sql(
            schema_context=schema_ctx,
            question=question,
            company_code="",
            fiscal_year="",
            history=history,
            extra_context=extra_context,
        )

        # Safety validation
        safety = validate_sql(sql_raw)
        if not safety.is_safe:
            log.info(f"[PIPELINE] LLM SQL blocked: {safety.blocked_reason}")
            log_query(user_id, question, sql_raw, safety, success=False)
            return PipelineResult(
                answer="عذراً، لا يمكن تنفيذ هذا الاستعلام لأسباب أمنية.",
                sql=sql_raw,
                method="llm_controlled",
                safety_warnings=[safety.blocked_reason],
            )

        sql = safety.sql

        # Execute
        data, err = await _try_execute(sql)

        # Auto-fix loop: if SQL failed, ask LLM to fix
        if err:
            log.info(f"[PIPELINE] LLM SQL failed, auto-fixing: {err[:150]}")
            fix_question = (
                f"الاستعلام التالي فشل:\n{sql}\n\n"
                f"الخطأ: {err[:300]}\n\n"
                f"السؤال الأصلي: {question}\n\n"
                f"أعد كتابة SQL صحيح يجيب على السؤال. أرجع SQL فقط."
            )
            sql_raw = generate_sql(
                schema_context=schema_ctx,
                question=fix_question,
                company_code="",
                fiscal_year="",
                history=history,
            )
            safety = validate_sql(sql_raw)
            if safety.is_safe:
                sql = safety.sql
                data, err = await _try_execute(sql)

        if err:
            log_query(user_id, question, sql, safety, success=False, error=err)
            raise Exception(err)

        # Auto-retry LIKE for CHART_CODE
        if len(data) == 0:
            match = re.search(r"CHART_CODE\s*=\s*'?(\d+)'?", sql, re.IGNORECASE)
            if match:
                data, sql = await _try_like_fallback(sql, match.group(1))

        # Auto-retry LIKE for name columns when exact match returns 0
        if len(data) == 0:
            data, sql = await _try_name_like_fallback(sql)

        truncated = any(row.get("__truncated__") for row in data)
        data = [row for row in data if not row.get("__truncated__")]

        # Format answer
        answer = _safe_format_answer(
            question=question,
            data=data,
            sql=sql,
            history=history,
            truncated=truncated,
        )

        if truncated:
            answer += "\n\n---\n⚠️ النتائج مقتصرة على أول 500 سجل — يمكن تضييق نطاق البحث للحصول على نتائج أكثر دقة."

        log_query(user_id, question, sql, safety, success=True, rows=len(data))

        # CHANGE 3: reasoning validate/record REMOVED (no reasoning plan exists now).

        # Build chart: explicit request or auto-generate
        chart = None
        if _wants_chart(question):
            chart = _build_chart_data(data, question)
        elif len(data) >= 2:
            chart = auto_generate_chart(data, question, intent.domain)

        # Copilot enrichment
        if chart:
            _record_viz(intent.domain, intent.sub_intent, data, chart)
        suggestions = generate_suggestions(
            question=question,
            sub_intent=intent.sub_intent,
            domain=intent.domain,
            data=data,
            entities=intent.entities,
            row_count=len(data),
            has_chart=chart is not None,
        )
        insights = generate_insights(
            data=data,
            question=question,
            domain=intent.domain,
            sub_intent=intent.sub_intent,
            row_count=len(data),
        )

        return PipelineResult(
            answer=answer,
            sql=sql,
            row_count=len(data),
            method="llm_controlled",
            safety_warnings=safety.warnings,
            chart_data=chart,
            suggestions=suggestions,
            insights=insights,
        )

    except Exception as e:
        err_str = str(e)
        # Rate limit handling
        if "429" in err_str or "rate_limit" in err_str.lower() or "resourceexhausted" in err_str.lower():
            wait = re.search(r'try again in (\d+m[\d.]+s)', err_str)
            wait_msg = f" (انتظر {wait.group(1)})" if wait else ""
            return PipelineResult(
                answer=f"تم تجاوز حد الاستخدام المجاني — حاول بعد قليل{wait_msg}",
                method="error",
                error=err_str,
            )
        return PipelineResult(
            answer="حدث خطأ — حاول إعادة صياغة السؤال بشكل أوضح.",
            method="error",
            error=err_str,
        )


# ── Context-awareness helpers ─────────────────────────────────────

def _needs_history_context(intent: Intent, history: list) -> bool:
    """Detect questions that need conversation history to be properly understood.
    Uses the Intent.needs_history flag from the classifier (v2), plus fallback checks.
    """
    if not history or len(history) < 2:
        return False
    # Strong regex match (confidence >= 0.95) → trust the template, skip history
    if intent.confidence >= 0.95 and intent.source == "regex":
        return False
    # Intent classifier v2 detected contextual need
    if intent.needs_history:
        return True
    # Strong match from any source → trust it
    if intent.confidence >= 0.95:
        return False
    # Weak match (LLM or keyword) with no entity anchors → likely contextual
    anchor_entities = {"account_code", "invoice_id", "customer_name",
                       "store_name", "employee_name"}
    if not (anchor_entities & set(intent.entities.keys())):
        return True
    return False


# ── Helpers ────────────────────────────────────────────────────────

async def _try_execute(sql: str) -> tuple[list[dict], Optional[str]]:
    """Execute SQL and return (data, error_or_none). Uses cache when available."""
    cache_key = make_sql_key(sql)

    # Check cache first
    cached = sql_cache.get(cache_key)
    if cached is not None:
        log.info(f"[PIPELINE] Cache HIT for SQL ({len(cached)} rows)")
        return cached, None

    try:
        data = await execute_query(sql)
        # Cache successful results (only non-empty and non-error)
        if data is not None:
            sql_cache.set(cache_key, data)
        return data, None
    except Exception as e:
        return [], str(e)


_NAME_COLUMNS = re.compile(
    r"((?:STORE_NAME|CUST_NAME|ITEMNAME|EMP_NAME_AR|CHART_NAME_A|CHART_NAME_E"
    r"|CUST_NAME_E|STORE_NAME_EN|ITEM_NAME_E))\s*=\s*(?:N)?'([^']+)'",
    re.IGNORECASE,
)


async def _try_name_like_fallback(sql: str) -> tuple[list[dict], str]:
    """Replace = with LIKE for name columns. Two levels:
    1. LIKE '%full value%'
    2. Split words: LIKE '%word1%' AND LIKE '%word2%' (fuzzy)
    """
    matches = list(_NAME_COLUMNS.finditer(sql))
    if not matches:
        return [], sql

    # Level 1: full value LIKE
    sql_like = sql
    for m in matches:
        col, val = m.group(1), m.group(2)
        sql_like = sql_like.replace(m.group(0), f"{col} LIKE '%{val}%'")

    try:
        data = await execute_query(sql_like)
        if data:
            log.info(f"[PIPELINE] Name LIKE fallback succeeded: {len(data)} rows")
            return data, sql_like
    except Exception:
        pass

    # Level 2: split into words — each word matched separately
    sql_words = sql
    for m in matches:
        col, val = m.group(1), m.group(2)
        words = [w for w in val.split() if len(w) > 1 and w not in ("ال", "في", "من", "على")]
        if words:
            conditions = " AND ".join(f"{col} LIKE '%{w}%'" for w in words)
            sql_words = sql_words.replace(m.group(0), f"({conditions})")
        else:
            sql_words = sql_words.replace(m.group(0), f"{col} LIKE '%{val}%'")

    try:
        data = await execute_query(sql_words)
        if data:
            log.info(f"[PIPELINE] Name WORDS fallback succeeded: {len(data)} rows")
            return data, sql_words
    except Exception:
        pass

    return [], sql


async def _try_like_fallback(sql: str, code: str) -> tuple[list[dict], str]:
    """Try CHART_CODE LIKE fallback when exact match returns 0 results."""
    match = re.search(r"CHART_CODE\s*=\s*'?" + re.escape(code) + r"'?", sql, re.IGNORECASE)
    if match:
        sql_like = sql.replace(match.group(0), f"CHART_CODE LIKE '{code}%'")
        try:
            data = await execute_query(sql_like)
            if data:
                return data, sql_like
        except Exception:
            pass
    return [], sql


# ── Fallback formatter (no LLM needed) ────────────────────────────

# Arabic-friendly column name mapping
_COL_LABELS = {
    "STORE_NAME": "المخزن", "STORE_NAME_EN": "المخزن (EN)", "STORE_CODE": "كود المخزن",
    "ITEMNAME": "اسم الصنف", "ITEM_NAME": "اسم الصنف", "ITEM_NAME_E": "اسم الصنف (EN)",
    "ITEMID": "كود الصنف", "GROUPNAME": "المجموعة",
    "QTY": "الكمية", "CURRENT_QTY": "الكمية الحالية", "PRICE": "السعر",
    "TOTAL_QTY": "إجمالي الكمية", "AVG_COST": "متوسط التكلفة",
    "SELLPRICE": "سعر البيع", "TOTAL_BUYPRICE": "سعر الشراء",
    "CUST_NAME": "العميل", "CUST_NAME_E": "العميل (EN)", "CUSTID": "كود العميل",
    "CUST_TYPE_DESC": "النوع",
    "CHART_CODE": "كود الحساب", "CHART_NAME_A": "اسم الحساب", "CHART_NAME_E": "الاسم (EN)",
    "CHART_TYPE": "نوع الحساب", "CHART_NATURE": "طبيعة الحساب",
    "PARENT_CHART_CODE": "الحساب الأب", "CHART_LEVEL": "المستوى",
    "CHART_OPEN_LOC": "الرصيد الافتتاحي", "OPENING_BALANCE": "الرصيد الافتتاحي",
    "TRANS_TYPE_NAME": "نوع الحركة", "TRANS_TYPE": "نوع الحركة",
    "TRANS_NAME": "اسم الحركة", "TRANS_CODE": "رقم الإذن",
    "INVID": "رقم الفاتورة", "INVDATE": "التاريخ", "INV_TYPE": "نوع الفاتورة",
    "RETURN_STATUS": "حالة المرتجع",
    "FINALTOTAL": "الإجمالي", "INVTOTAL": "المجموع", "TAX": "الضريبة",
    "SDAD": "المدفوع", "LINE_TOTAL": "إجمالي السطر",
    "EMP_NAME_AR": "الموظف", "EMP_NAME_EN": "الموظف (EN)", "EMP_ID": "كود الموظف",
    "HIRE_DATE": "تاريخ التعيين", "END_SERVICE_FLG": "نهاية الخدمة",
    "NOTES": "ملاحظات", "DISCOUNT": "الخصم",
    "TRANS_DATE": "تاريخ الحركة",
    "VOUCHER_CODE": "رقم القيد", "VOUCHER_DATE": "تاريخ القيد", "VOUCHER_DESC": "البيان",
    "DEBIT": "المدين", "CREDIT": "الدائن", "AMOUNT": "المبلغ",
    "TOTAL_DEBIT": "إجمالي المدين", "TOTAL_CREDIT": "إجمالي الدائن",
    "BALANCE": "الرصيد",
    "INVOICE_COUNT": "عدد الفواتير", "TOTAL_SALES": "إجمالي المبيعات",
    "TOTAL_PURCHASES": "إجمالي المشتريات", "TOTAL_TAX": "إجمالي الضريبة",
    "EMPLOYEE_COUNT": "عدد الموظفين", "OUTSTANDING": "المستحق",
    "OPEN_BALANCE": "الرصيد الافتتاحي", "CREDIT_LIMIT": "حد الائتمان",
    "TAX_NO": "الرقم الضريبي", "ACTIVE": "الحالة",
    "UNIT_NAME": "الوحدة", "SALE_DATE": "تاريخ البيع",
    "MAIN_STORE": "المخزن الرئيسي", "BAR_CODE": "الباركود",
}


def _format_data_as_table(data: list[dict], question: str = "") -> str:
    """Format query data as a markdown table without LLM — used as rate-limit fallback."""
    if not data:
        return "لم يتم العثور على بيانات مطابقة لسؤالك."

    cols = list(data[0].keys())
    # Translate column headers
    headers = [_COL_LABELS.get(c.upper(), c) for c in cols]

    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")

    for row in data[:50]:  # Cap at 50 rows for readability
        cells = []
        for c in cols:
            v = row.get(c, "")
            if v is None:
                cells.append("-")
            elif isinstance(v, float):
                cells.append(f"{v:,.1f}" if v != int(v) else f"{int(v):,}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")

    result = "\n".join(lines)
    if len(data) > 50:
        result += f"\n\n---\nتم عرض أول 50 سجل من إجمالي {len(data):,} سجل."
    return result


def _comment_context_for_sql(sql: str) -> str:
    """RC5: Build a compact 'column = business meaning' context from
    justclick_comments.sql for the tables referenced in the SQL. Used to ground
    the answer narrative — including on the TEMPLATE path, which otherwise never
    sees any business meaning from the comments.
    """
    try:
        from schema_loader import _column_comments
        tbls = re.findall(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', sql, re.IGNORECASE)
        seen: set[str] = set()
        lines: list[str] = []
        for t in tbls:
            t = t.upper()
            if t in seen:
                continue
            seen.add(t)
            for col, desc in list(_column_comments.get(t, {}).items())[:8]:
                head = re.split(r'[.\n]', desc, 1)[0].strip()
                if head:
                    lines.append(f"{col} = {head[:60]}")
        return " | ".join(lines[:25])
    except Exception:
        return ""


def _safe_format_answer(question, data, sql, history=None, truncated=False):
    """Format with executive AI copilot style. Falls back to local on error."""
    if not data:
        return _smart_empty_response(question)
    # Use LLM executive formatting for reasonable data sizes
    if len(data) <= 50:
        try:
            extra = _comment_context_for_sql(sql)   # RC5: comment-grounded narrative
            return format_answer(question, data, sql, history, truncated, extra)
        except Exception as e:
            log.info(f"[PIPELINE] LLM format fallback to local: {e}")
    # Fallback: enhanced local formatting
    return _format_data_as_table(data, question)


def _smart_empty_response(question: str) -> str:
    """Generate a contextual, positive empty-state response."""
    q_lower = question.lower()

    # Time-specific empty states
    if any(kw in q_lower for kw in ["اليوم", "today"]):
        return "لا توجد حركات مسجلة اليوم حتى الآن. يمكن الاطلاع على بيانات أمس أو هذا الأسبوع."
    if any(kw in q_lower for kw in ["هذا الشهر", "this month"]):
        return "لم تُسجل بيانات لهذا الشهر بعد. جرّب الاطلاع على الشهر الماضي."

    # Positive empty states (no results = good news)
    if any(kw in q_lower for kw in ["متأخر", "overdue", "مديون"]):
        return "لا توجد مديونيات متأخرة — وضع التحصيل ممتاز."
    if any(kw in q_lower for kw in ["مرتجع", "return"]):
        return "لا توجد مرتجعات في هذه الفترة — مؤشر إيجابي على جودة المبيعات."
    if any(kw in q_lower for kw in ["منخفض", "نفاد", "أقل من"]):
        return "جميع الأصناف بمستويات مخزون كافية — لا توجد تنبيهات حالياً."

    # Default with suggestion
    return "لم أجد بيانات مطابقة. جرّب تعديل الصياغة أو توسيع نطاق البحث."


# ── Chart helpers ──────────────────────────────────────────────────

_CHART_REQUEST = re.compile(
    r"(رسم\s*بياني|chart|graph|مخطط|ارسم|رسم|بياني|pie|bar|line|دائري|أعمدة|خطي)",
    re.IGNORECASE,
)

_CHART_TYPE_MAP = {
    "pie": ["دائري", "pie", "نسب"],
    "line": ["خطي", "line", "trend", "اتجاه"],
    "bar": [],  # default
}


def _wants_chart(question: str) -> bool:
    """Detect if the user is asking for a chart/visualization."""
    return bool(_CHART_REQUEST.search(question))


def _detect_chart_type(question: str) -> str:
    """Detect which chart type the user wants."""
    q = question.lower()
    for chart_type, keywords in _CHART_TYPE_MAP.items():
        for kw in keywords:
            if kw in q:
                return chart_type
    return "bar"


def _build_chart_data(data: list[dict], question: str) -> Optional[dict]:
    """
    Build Chart.js-compatible data from query results.
    Heuristic: first string column = labels, first numeric column = values.
    """
    if not data or len(data) == 0:
        return None

    # Find label column (first string-like) and value column (first numeric)
    sample = data[0]
    label_col = None
    value_cols = []

    for col, val in sample.items():
        if label_col is None and isinstance(val, str):
            label_col = col
        elif isinstance(val, (int, float)) and val is not None:
            value_cols.append(col)

    # If no string column, try to use the first column as labels
    if label_col is None:
        cols = list(sample.keys())
        if len(cols) >= 2:
            label_col = cols[0]
            value_cols = [c for c in cols[1:] if isinstance(sample.get(c), (int, float))]

    if not label_col or not value_cols:
        return None

    # Use first value column for chart
    val_col = value_cols[0]

    labels = []
    values = []
    for row in data[:20]:  # max 20 items for readability
        lbl = str(row.get(label_col, ""))
        if len(lbl) > 25:
            lbl = lbl[:22] + "..."
        labels.append(lbl)
        v = row.get(val_col, 0)
        values.append(float(v) if v is not None else 0)

    chart_type = _detect_chart_type(question)

    # Color palette
    colors = [
        "oklch(0.55 0.18 260)",   # blue
        "oklch(0.62 0.15 155)",   # green
        "oklch(0.60 0.18 25)",    # red
        "oklch(0.65 0.15 70)",    # orange
        "oklch(0.55 0.15 310)",   # purple
        "oklch(0.60 0.12 200)",   # teal
        "oklch(0.65 0.10 90)",    # yellow
        "oklch(0.50 0.15 340)",   # pink
    ]
    bg_colors = colors[:len(labels)]
    while len(bg_colors) < len(labels):
        bg_colors.extend(colors)
    bg_colors = bg_colors[:len(labels)]

    # Translate column name for display
    col_labels = {
        "total_sales": "إجمالي المبيعات",
        "total_debit": "المدين",
        "total_credit": "الدائن",
        "balance": "الرصيد",
        "total_qty": "الكمية",
        "invoice_count": "عدد الفواتير",
        "outstanding": "المستحق",
        "current_qty": "الكمية الحالية",
        "employee_count": "عدد الموظفين",
        "total_purchases": "إجمالي المشتريات",
    }
    dataset_label = col_labels.get(val_col, val_col)

    return {
        "type": chart_type,
        "labels": labels,
        "datasets": [{
            "label": dataset_label,
            "data": values,
            "backgroundColor": bg_colors,
        }],
    }


# ── Dashboard detection helpers ───────────────────────────────────

_DASHBOARD_REQUEST = re.compile(
    r"(لوحة|dashboard|تحليلات|analytics|لوحات|داش\s*بورد|داشبورد|إحصائيات|احصائيات)",
    re.IGNORECASE,
)


def _wants_dashboard(question: str) -> bool:
    return bool(_DASHBOARD_REQUEST.search(question))


async def _handle_dashboard(question: str, history: list = None) -> Optional[PipelineResult]:
    """Handle dashboard request — tries explicit match first, then infers from conversation history."""
    dash_id = find_dashboard_by_query(question)

    # If no explicit match, infer the domain from conversation history
    if not dash_id and history:
        recent_text = " ".join(msg.get("content", "")[:200] for msg in history[-6:])
        dash_id = find_dashboard_by_query(recent_text)
        if dash_id:
            log.info(f"[PIPELINE] Dashboard inferred from conversation history: {dash_id}")

    if not dash_id:
        return None  # No dashboard matched — caller falls back to data query

    # Check dashboard cache
    d_key = make_dash_key(dash_id)
    cached_data = dash_cache.get(d_key)
    if cached_data is not None:
        log.info(f"[PIPELINE] Dashboard cache HIT: {dash_id}")
        data = cached_data
    else:
        data = await execute_dashboard(dash_id)
        if data:
            dash_cache.set(d_key, data)

    if not data:
        return PipelineResult(answer="حدث خطأ في تحميل اللوحة.", method="error")

    kpis = [w for w in data["widgets"] if w.get("type") == "kpi" and w.get("data")]
    lines = [data["title"]]
    for k in kpis:
        v = k["data"].get("value", 0)
        fmt = k["data"].get("format", "number")
        if fmt == "currency":
            disp = f"{v:,.2f}"
        elif fmt == "percent":
            disp = f"{v:.1f}%"
        else:
            disp = f"{v:,.0f}"
        lines.append(f"{k['title']}: {disp}")

    return PipelineResult(
        answer="\n".join(lines),
        method="dashboard",
        widgets=data["widgets"],
    )


# ══════════════════════════════════════════════════════════════════
# ERP Operator Handlers
# ══════════════════════════════════════════════════════════════════

async def _handle_workflow_query(
    workflow_type: str,
    user_id: str,
    company_code: str,
) -> Optional[PipelineResult]:
    """Handle workflow-related queries (pending approvals, status checks)."""
    try:
        if workflow_type == "pending_approvals":
            approvals = await get_pending_approvals(user_id=user_id, company_code=company_code)
            if not approvals:
                return PipelineResult(
                    answer="لا توجد طلبات معلقة حالياً.",
                    method="workflow",
                    suggestions=["اعرض سجل الاعتمادات", "ملخص الطلبات"],
                )
            # Format approvals as structured response
            lines = [f"**الطلبات المعلقة** ({len(approvals)} طلب):\n"]
            for i, req in enumerate(approvals[:10], 1):
                req_id = req.get("REQUEST_ID", "")
                req_type = req.get("REQUEST_TYPE", "")
                desc = req.get("DESCRIPTION", "")[:80]
                amount = req.get("AMOUNT", "")
                amount_str = f" | المبلغ: {float(amount):,.2f}" if amount else ""
                lines.append(f"{i}. **طلب #{req_id}** — {req_type}{amount_str}")
                if desc:
                    lines.append(f"   {desc}")
            if len(approvals) > 10:
                lines.append(f"\n... و {len(approvals) - 10} طلبات أخرى")
            lines.append("\n💡 لاعتماد طلب، قل: *اعتمد الطلب رقم [X]*")
            return PipelineResult(
                answer="\n".join(lines),
                method="workflow",
                row_count=len(approvals),
                suggestions=["اعتمد الطلب", "ارفض الطلب", "تفاصيل الطلب"],
            )

        elif workflow_type.startswith("request_status:"):
            request_id = workflow_type.split(":")[1]
            status = await get_request_status(request_id, company_code)
            if not status:
                return PipelineResult(
                    answer=f"لم أجد طلب برقم {request_id}.",
                    method="workflow",
                )
            # Format status
            lines = [f"**حالة الطلب #{request_id}**\n"]
            lines.append(f"- النوع: {status.get('REQUEST_TYPE', '-')}")
            lines.append(f"- الحالة: {status.get('STATUS_LABEL', status.get('STATUS', '-'))}")
            lines.append(f"- الطالب: {status.get('REQUESTED_BY', '-')}")
            lines.append(f"- التاريخ: {status.get('REQUESTED_AT', '-')}")
            if status.get("AMOUNT"):
                lines.append(f"- المبلغ: {float(status['AMOUNT']):,.2f}")
            if status.get("APPROVED_BY"):
                lines.append(f"- المعتمد: {status['APPROVED_BY']}")
            if status.get("NOTES"):
                lines.append(f"- ملاحظات: {status['NOTES']}")
            return PipelineResult(
                answer="\n".join(lines),
                method="workflow",
                suggestions=["اعتمد الطلب", "ارفض الطلب", "اعرض الطلبات المعلقة"],
            )

        elif workflow_type == "request_status":
            # General status query without specific ID
            summary = await get_approval_summary(company_code)
            lines = ["**ملخص الطلبات:**\n"]
            lines.append(f"- معلقة: {summary.get('pending', 0)}")
            lines.append(f"- معتمدة: {summary.get('approved', 0)}")
            lines.append(f"- مرفوضة: {summary.get('rejected', 0)}")
            lines.append(f"- الإجمالي: {summary.get('total', 0)}")
            return PipelineResult(
                answer="\n".join(lines),
                method="workflow",
                suggestions=["اعرض الطلبات المعلقة", "اعرض سجل الاعتمادات"],
            )

    except Exception as e:
        log.warning(f"[PIPELINE] Workflow handler error: {e}")
        return None

    return None


async def _handle_executive_report(
    report_type: str,
    company_code: str,
    fiscal_year: str,
) -> Optional[PipelineResult]:
    """Handle executive report generation."""
    try:
        report = await generate_executive_report(
            report_type=report_type,
            company_code=company_code,
            fiscal_year=fiscal_year,
        )
        chat_text = format_report_for_chat(report)

        # Build chart from trends if available
        chart_data = None
        if report.trends:
            trend = report.trends[0]
            chart_data = {
                "type": trend.get("type", "line"),
                "labels": trend.get("labels", []),
                "datasets": [{
                    "label": trend.get("label", ""),
                    "data": trend.get("values", []),
                    "backgroundColor": "oklch(0.55 0.18 260)",
                    "borderColor": "oklch(0.55 0.18 260)",
                }],
            }

        return PipelineResult(
            answer=chat_text,
            method="report",
            chart_data=chart_data,
            report_data=report.to_dict(),
            suggestions=[
                "صدّر التقرير PDF",
                "صدّر التقرير Excel",
                "تفاصيل أكثر",
                "قارن مع الشهر الماضي",
            ],
        )
    except Exception as e:
        log.warning(f"[PIPELINE] Executive report error: {e}")
        return None


def _handle_navigation(nav_pages: list[dict]) -> Optional[PipelineResult]:
    """Handle APEX navigation requests."""
    if not nav_pages:
        return None

    lines = ["**الصفحات المتاحة:**\n"]
    for page in nav_pages[:5]:
        title = page.get("title_ar", "")
        url = page.get("url", "")
        icon = page.get("icon", "")
        lines.append(f"- 📄 **{title}** — [{url}]({url})")

    if len(nav_pages) == 1:
        page = nav_pages[0]
        lines = [f"🔗 **{page.get('title_ar', '')}**"]
        lines.append(f"\nرابط مباشر: {page.get('url', '')}")

    return PipelineResult(
        answer="\n".join(lines),
        method="navigation",
        navigation_links=nav_pages,
        suggestions=[
            {"label": "المبيعات", "query": "إجمالي المبيعات اليوم", "icon": "finance"},
            {"label": "أعلى العملاء", "query": "أعلى 5 عملاء في المبيعات", "icon": "ranking"},
        ],
    )
