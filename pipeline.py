"""
pipeline.py — ERP Intelligence Router Pipeline
The central engine that orchestrates:
  Intent Classification -> Template Matching -> Safe SQL -> Execution -> Formatting
"""
import re
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


@dataclass
class PipelineResult:
    answer: str
    sql: str = ""
    row_count: int = 0
    intent: Optional[Intent] = None
    template_used: str = ""
    method: str = ""           # template | llm_controlled | greeting | help | error | dashboard
    execution_time_ms: int = 0
    safety_warnings: list[str] = field(default_factory=list)
    chart_data: Optional[dict] = None   # {type, labels, datasets} for Chart.js
    widgets: Optional[list] = None      # multi-widget response (KPIs + charts + tables in chat)


# ── Greeting responses ────────────────────────────────────────────
_GREETING_RESPONSES = [
    "اهلاً! انا المساعد الذكي لنظام JustClick. اسألني عن بيانات الحسابات، الفواتير، المخزون، العملاء، أو الموظفين.",
]

_HELP_RESPONSE = """يمكنني مساعدتك في الاستفسار عن:

**الحسابات**: رصيد حساب، كشف حساب، ميزان المراجعة، شجرة الحسابات
**الفواتير**: تفاصيل فاتورة، إجمالي المبيعات، أكثر العملاء شراءً
**المخزون**: رصيد المخزون، بيانات الأصناف، حركات المخزن
**العملاء**: قائمة العملاء، بيانات عميل، المديونيات
**الموظفين**: عدد الموظفين، قائمة الموظفين

أمثلة:
- رصيد حساب 1101
- تفاصيل فاتورة 1000016
- إجمالي المبيعات اليوم
- أكثر 5 عملاء شراءً
- عدد الموظفين النشطين"""


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

    # ── Step 0: Company access validation ──
    if company_code:
        has_access = await validate_company_access(user_id, company_code)
        if not has_access:
            return PipelineResult(
                answer="ليس لديك صلاحية على هذه الشركة.",
                method="error",
            )

    # ── Step 1: Get conversation context ──
    session_history = get_history_messages(user_id)
    context_entities = get_context_entities(user_id)

    # ── Step 2: Classify intent ──
    intent = classify_intent(question, session_history)
    log.info(f"[PIPELINE] intent={intent.category} domain={intent.domain} "
             f"sub={intent.sub_intent} entities_keys={list(intent.entities.keys())}")

    # Merge context entities with newly extracted ones
    merged_entities = {**context_entities, **intent.entities}
    intent.entities = merged_entities

    # Record user turn
    add_user_turn(user_id, question, intent.entities, intent.sub_intent)

    # ── Step 3: Route by intent category ──
    result: PipelineResult

    if intent.category == "greeting":
        result = PipelineResult(
            answer=_GREETING_RESPONSES[0],
            intent=intent,
            method="greeting",
        )

    elif intent.category == "help":
        result = PipelineResult(
            answer=_HELP_RESPONSE,
            intent=intent,
            method="help",
        )

    elif _wants_dashboard(question):
        log.debug(f"[PIPELINE] Dashboard matched for: {question}")
        result = await _handle_dashboard(question, session_history)
        if not result:
            # No dashboard matched — fall through to data query with history
            log.info("[PIPELINE] Dashboard detected but no match — using LLM data query path")
            result = await _handle_data_query(
                question=question,
                intent=intent,
                user_id=user_id,
                company_code=company_code,
                fiscal_year=fiscal_year,
                history=history or session_history,
            )

    else:
        log.debug(f"[PIPELINE] Data query path for: {question}")
        # Data query path (data_query, aggregation, comparison, detail_lookup)
        result = await _handle_data_query(
            question=question,
            intent=intent,
            user_id=user_id,
            company_code=company_code,
            fiscal_year=fiscal_year,
            history=history or session_history,
        )

    # Record assistant turn
    add_assistant_turn(
        user_id, result.answer, result.sql, result.row_count, intent.entities
    )

    result.execution_time_ms = int((time.time() - start) * 1000)
    return result


async def _handle_data_query(
    question: str,
    intent: Intent,
    user_id: str,
    company_code: str,
    fiscal_year: str,
    history: list,
) -> PipelineResult:
    """Handle data query: template match first, then LLM fallback."""

    # ── Try template matching ──
    if intent.sub_intent:
        # If question is contextual (LLM-classified, no entities, has history)
        # skip template and go to LLM-controlled which uses conversation history
        if _needs_history_context(intent, history):
            log.info(f"[PIPELINE] Contextual question (confidence={intent.confidence:.2f}), "
                     f"skipping template → LLM with history")
        else:
            template = find_template(intent.sub_intent, intent.entities)
            log.info(f"[PIPELINE] sub_intent={intent.sub_intent} template={'FOUND:'+template.name if template else 'NONE'}")
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
                    result.intent = intent
                    return result
    else:
        log.info("[PIPELINE] no sub_intent, going to LLM")

    # ── Fallback: controlled LLM SQL generation ──
    result = await _execute_llm_controlled(
        question=question,
        intent=intent,
        user_id=user_id,
        company_code=company_code,
        fiscal_year=fiscal_year,
        history=history,
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
    """Execute a query template with extracted parameters."""
    try:
        # Check required params
        missing = [p for p in template.required_params
                   if p not in entities and p not in template.param_defaults]
        if missing:
            log.info(f"[PIPELINE] Template {template.name} missing params: {missing}")
            return None

        # Render SQL from template
        sql = render_template(template, entities)

        # Inject company/fiscal filters
        sql = inject_company_filter(sql, company_code, fiscal_year)
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

        # Build chart if requested
        chart = _build_chart_data(data, question) if _wants_chart(question) else None

        return PipelineResult(
            answer=answer,
            sql=sql,
            row_count=len(data),
            template_used=template.name,
            method="template",
            safety_warnings=safety.warnings,
            chart_data=chart,
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

        sql_raw = generate_sql(
            schema_context=schema_ctx,
            question=question,
            company_code=company_code,
            fiscal_year=fiscal_year,
            history=history,
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

        # Inject company/fiscal filters
        sql = inject_company_filter(sql, company_code, fiscal_year)

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
                company_code=company_code,
                fiscal_year=fiscal_year,
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

        # Build chart if requested
        chart = _build_chart_data(data, question) if _wants_chart(question) else None

        return PipelineResult(
            answer=answer,
            sql=sql,
            row_count=len(data),
            method="llm_controlled",
            safety_warnings=safety.warnings,
            chart_data=chart,
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
            )
        return PipelineResult(
            answer="حدث خطأ — حاول إعادة صياغة السؤال بشكل أوضح.",
            method="error",
        )


# ── Context-awareness helpers ─────────────────────────────────────

def _needs_history_context(intent: Intent, history: list) -> bool:
    """Detect questions that need conversation history to be properly understood.
    Uses the Intent.needs_history flag from the classifier (v2), plus fallback checks.
    """
    if not history or len(history) < 2:
        return False
    # Intent classifier v2 detected contextual need
    if intent.needs_history:
        return True
    # Strong regex match (confidence >= 0.95) → trust the template
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
    "STORE_NAME": "المخزن", "ITEMNAME": "اسم الصنف", "ITEM_NAME": "اسم الصنف",
    "QTY": "الكمية", "CURRENT_QTY": "الكمية الحالية", "PRICE": "السعر",
    "TOTAL_QTY": "إجمالي الكمية", "CUST_NAME": "العميل", "CHART_NAME_A": "اسم الحساب",
    "TRANS_TYPE_NAME": "نوع الحركة", "INVID": "رقم الفاتورة", "INVDATE": "التاريخ",
    "FINALTOTAL": "الإجمالي", "STORE_CODE": "كود المخزن", "ITEMID": "كود الصنف",
    "EMP_NAME_AR": "الموظف", "NOTES": "ملاحظات", "DISCOUNT": "الخصم",
    "TRANS_CODE": "رقم الإذن", "TRANS_DATE": "تاريخ الحركة",
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


def _safe_format_answer(question, data, sql, history=None, truncated=False):
    """Format data as markdown table directly — saves LLM tokens."""
    return _format_data_as_table(data, question)


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
