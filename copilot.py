"""
copilot.py — Enterprise AI Copilot Intelligence Layer
Generates intelligent suggestions, contextual insights, business reasoning,
and auto-visualizations. Rule-based for instant enrichment (no extra LLM calls).
"""
import re
import logging
from typing import Optional

log = logging.getLogger("copilot")


# ═══════════════════════════════════════════════════════════════════
# Suggestion Engine — Contextual Follow-up Recommendations
# ═══════════════════════════════════════════════════════════════════

_DOMAIN_SUGGESTIONS = {
    "sales": [
        {"label": "مقارنة مع الشهر الماضي", "query": "مقارنة المبيعات مع الشهر الماضي", "icon": "compare"},
        {"label": "توزيع حسب الفروع", "query": "توزيع المبيعات حسب الفروع", "icon": "branch"},
        {"label": "رسم بياني للمبيعات", "query": "ارسم رسم بياني للمبيعات", "icon": "chart"},
        {"label": "أعلى المنتجات مبيعاً", "query": "أعلى 10 منتجات مبيعاً", "icon": "ranking"},
        {"label": "اتجاه المبيعات الشهري", "query": "اتجاه المبيعات خلال آخر 6 شهور", "icon": "trend"},
    ],
    "inventory": [
        {"label": "أصناف منخفضة المخزون", "query": "الأصناف التي مخزونها أقل من 10", "icon": "alert"},
        {"label": "رسم بياني للمخزون", "query": "ارسم رسم بياني لأعلى الأصناف في المخزون", "icon": "chart"},
        {"label": "حركات المخزن اليوم", "query": "حركات المخزن اليوم", "icon": "movement"},
        {"label": "توزيع حسب المخازن", "query": "إجمالي المخزون حسب المخازن", "icon": "branch"},
    ],
    "accounting": [
        {"label": "ميزان المراجعة", "query": "ميزان المراجعة", "icon": "balance"},
        {"label": "الإيرادات والمصروفات", "query": "الإيرادات والمصروفات خلال آخر 6 شهور", "icon": "finance"},
        {"label": "رسم بياني للأرصدة", "query": "ارسم رسم بياني للإيرادات والمصروفات", "icon": "chart"},
        {"label": "تحليل صافي الربح", "query": "صافي الربح خلال آخر 6 شهور", "icon": "trend"},
    ],
    "customers": [
        {"label": "العملاء المتأخرين", "query": "العملاء المتأخرين في السداد", "icon": "alert"},
        {"label": "أعلى 5 عملاء", "query": "أعلى 5 عملاء في المبيعات", "icon": "ranking"},
        {"label": "رسم بياني للعملاء", "query": "ارسم رسم بياني لأعلى العملاء في المبيعات", "icon": "chart"},
        {"label": "تحليل المديونيات", "query": "ملخص مديونيات العملاء", "icon": "finance"},
    ],
    "hr": [
        {"label": "توزيع حسب الأقسام", "query": "توزيع الموظفين حسب الأقسام", "icon": "branch"},
        {"label": "الموظفين الجدد", "query": "الموظفين المعينين خلال آخر 3 شهور", "icon": "new"},
        {"label": "لوحة الموظفين", "query": "لوحة الموظفين", "icon": "dashboard"},
    ],
}

_INTENT_SUGGESTIONS = {
    "account_balance": [
        {"label": "كشف حساب تفصيلي", "query": "كشف حساب {account_code} خلال آخر 3 شهور", "icon": "detail"},
        {"label": "رسم بياني للحركات", "query": "ارسم رسم بياني لحركات حساب {account_code}", "icon": "chart"},
        {"label": "الحسابات الفرعية", "query": "الحسابات الفرعية لحساب {account_code}", "icon": "tree"},
    ],
    "account_statement": [
        {"label": "ملخص الأرصدة", "query": "رصيد حساب {account_code}", "icon": "balance"},
        {"label": "رسم بياني للحركات", "query": "ارسم رسم بياني لحركات حساب {account_code} الشهرية", "icon": "chart"},
        {"label": "مقارنة بالفترة السابقة", "query": "مقارنة حركات حساب {account_code} مع الفترة السابقة", "icon": "compare"},
    ],
    "top_customers": [
        {"label": "عرض كرسم بياني", "query": "ارسم رسم بياني لأعلى العملاء في المبيعات", "icon": "chart"},
        {"label": "تفاصيل أعلى عميل", "query": "تفاصيل فواتير أعلى عميل في المبيعات", "icon": "detail"},
        {"label": "المديونيات المستحقة", "query": "مديونيات أعلى 5 عملاء", "icon": "alert"},
    ],
    "total_sales": [
        {"label": "رسم بياني يومي", "query": "رسم بياني للمبيعات اليومية هذا الشهر", "icon": "chart"},
        {"label": "مقارنة بالأمس", "query": "مقارنة مبيعات اليوم بالأمس", "icon": "compare"},
        {"label": "حسب الفروع", "query": "المبيعات اليوم حسب الفروع", "icon": "branch"},
        {"label": "أعلى المنتجات", "query": "أعلى المنتجات مبيعاً اليوم", "icon": "ranking"},
    ],
    "total_purchases": [
        {"label": "أعلى الموردين", "query": "أعلى 5 موردين في المشتريات", "icon": "ranking"},
        {"label": "رسم بياني للمشتريات", "query": "ارسم رسم بياني للمشتريات الشهرية", "icon": "chart"},
        {"label": "مقارنة بالمبيعات", "query": "مقارنة المبيعات مع المشتريات هذا الشهر", "icon": "compare"},
    ],
    "revenue_expenses": [
        {"label": "رسم بياني خطي", "query": "ارسم رسم بياني للإيرادات والمصروفات", "icon": "chart"},
        {"label": "صافي الربح", "query": "صافي الربح خلال آخر 6 شهور", "icon": "trend"},
        {"label": "تفاصيل المصروفات", "query": "تفاصيل أعلى المصروفات هذا الشهر", "icon": "detail"},
    ],
    "inventory_balance": [
        {"label": "رسم بياني للمخزون", "query": "ارسم رسم بياني لأرصدة المخازن", "icon": "chart"},
        {"label": "أصناف منخفضة", "query": "الأصناف التي مخزونها أقل من 5", "icon": "alert"},
        {"label": "حركات المخزن", "query": "حركات المخزن خلال آخر أسبوع", "icon": "movement"},
    ],
    "employee_count": [
        {"label": "توزيع حسب الأقسام", "query": "عدد الموظفين حسب الأقسام", "icon": "branch"},
        {"label": "الموظفين الجدد", "query": "الموظفين المعينين هذا العام", "icon": "new"},
        {"label": "لوحة الموظفين", "query": "لوحة الموظفين", "icon": "dashboard"},
    ],
    "invoice_detail": [
        {"label": "فواتير العميل", "query": "كل فواتير هذا العميل", "icon": "detail"},
        {"label": "مبيعات اليوم", "query": "إجمالي المبيعات اليوم", "icon": "finance"},
        {"label": "المرتجعات", "query": "المرتجعات خلال آخر شهر", "icon": "alert"},
    ],
}


def generate_suggestions(
    question: str,
    sub_intent: str = "",
    domain: str = "",
    data: list = None,
    entities: dict = None,
    row_count: int = 0,
    has_chart: bool = False,
    method: str = "",
) -> list[dict]:
    """Generate contextual follow-up suggestions based on query context."""
    suggestions = []
    entities = entities or {}

    # For greetings/help — return starter suggestions
    if method in ("greeting", "help"):
        return GREETING_SUGGESTIONS[:4]

    # 1. Intent-specific suggestions (highest priority)
    if sub_intent and sub_intent in _INTENT_SUGGESTIONS:
        for s in _INTENT_SUGGESTIONS[sub_intent][:3]:
            query = s["query"]
            # Replace entity placeholders
            for key, val in entities.items():
                query = query.replace("{" + key + "}", str(val))
            # Remove unresolved placeholders
            query = re.sub(r"\{[^}]+\}", "", query).strip()
            suggestions.append({
                "label": s["label"],
                "query": query,
                "icon": s.get("icon", "suggest"),
            })

    # 2. Domain suggestions (fill remaining)
    if domain and domain in _DOMAIN_SUGGESTIONS and len(suggestions) < 4:
        for s in _DOMAIN_SUGGESTIONS[domain]:
            if len(suggestions) >= 4:
                break
            if not any(existing["label"] == s["label"] for existing in suggestions):
                suggestions.append(s)

    # 3. Data-shape based suggestions
    if data and len(suggestions) < 4 and not has_chart:
        shape = _detect_data_shape(data)
        shape_suggestions = _get_shape_suggestions(shape, question)
        for s in shape_suggestions:
            if len(suggestions) >= 4:
                break
            if not any(existing["label"] == s["label"] for existing in suggestions):
                suggestions.append(s)

    # 4. Universal fallback
    if not suggestions:
        suggestions = [
            {"label": "لوحة المبيعات", "query": "لوحة المبيعات", "icon": "dashboard"},
            {"label": "إجمالي المبيعات", "query": "إجمالي المبيعات اليوم", "icon": "finance"},
            {"label": "أعلى 5 عملاء", "query": "أعلى 5 عملاء في المبيعات", "icon": "ranking"},
        ]

    return suggestions[:4]


def _detect_data_shape(data: list) -> str:
    """Detect data shape for context-aware suggestions."""
    if not data:
        return "empty"
    if len(data) == 1:
        cols = list(data[0].keys())
        numeric_cols = [c for c in cols if isinstance(data[0].get(c), (int, float))]
        if len(numeric_cols) <= 2 and len(cols) <= 3:
            return "single_value"
        return "single_record"

    sample = data[0]
    for col in sample.keys():
        col_upper = str(col).upper()
        if any(kw in col_upper for kw in ["DATE", "MONTH", "YEAR", "الشهر", "التاريخ"]):
            return "time_series"

    cols = list(sample.keys())
    if len(cols) >= 2:
        numeric_cols = [c for c in cols if isinstance(sample.get(c), (int, float))]
        if numeric_cols and len(data) <= 20:
            return "ranking"

    return "tabular"


def _get_shape_suggestions(shape: str, question: str) -> list[dict]:
    """Get suggestions based on data shape."""
    if shape == "single_value":
        return [
            {"label": "رسم بياني للاتجاه", "query": f"رسم بياني اتجاه {question}", "icon": "trend"},
            {"label": "مقارنة مع فترة سابقة", "query": f"مقارنة {question} مع الشهر الماضي", "icon": "compare"},
        ]
    elif shape == "ranking":
        return [
            {"label": "عرض كرسم بياني", "query": f"ارسم رسم بياني لـ {question}", "icon": "chart"},
        ]
    elif shape == "time_series":
        return [
            {"label": "رسم بياني خطي", "query": f"ارسم رسم بياني خطي لـ {question}", "icon": "chart"},
        ]
    elif shape == "tabular":
        return [
            {"label": "ملخص تنفيذي", "query": f"ملخص تنفيذي لـ {question}", "icon": "summary"},
        ]
    return []


# ═══════════════════════════════════════════════════════════════════
# Insight Engine — Contextual Business Intelligence
# ═══════════════════════════════════════════════════════════════════

def generate_insights(
    data: list,
    question: str = "",
    domain: str = "",
    sub_intent: str = "",
    row_count: int = 0,
) -> list[dict]:
    """Generate contextual business insights with reasoning."""
    if not data:
        if row_count == 0:
            return [_empty_state_insight(question, domain)]
        return []

    effective_count = row_count if row_count > 0 else len(data)
    insights = []

    # Single-value contextual insights
    if len(data) == 1 and effective_count <= 1:
        row = data[0]
        for col, val in row.items():
            if isinstance(val, (int, float)) and val != 0:
                insight = _single_value_insight(col, val, domain, question)
                if insight:
                    insights.append(insight)
                    break

    # Multi-row analysis
    elif len(data) >= 3:
        sample = data[0]
        numeric_cols = [c for c in sample.keys()
                        if isinstance(sample.get(c), (int, float)) and sample.get(c) is not None]

        for col in numeric_cols[:2]:
            values = [row.get(col, 0) for row in data
                      if isinstance(row.get(col), (int, float))]
            if not values:
                continue

            # Concentration analysis
            concentration = _concentration_insight(col, values, data)
            if concentration:
                insights.append(concentration)

            # Trend analysis (if time series)
            trend = _trend_insight(col, values, data)
            if trend:
                insights.append(trend)

            # Variance analysis
            variance = _variance_insight(col, values, data)
            if variance and len(insights) < 3:
                insights.append(variance)

    # Large result set notice
    if effective_count >= 50 and len(insights) < 3:
        insights.append({
            "type": "info",
            "text": f"يُعرض {min(effective_count, 200)} سجل — يمكن تضييق النطاق للحصول على تحليل أدق",
            "icon": "info",
        })

    return insights[:3]


def _empty_state_insight(question: str, domain: str) -> dict:
    """Smart empty state — explain why and suggest alternatives."""
    q_lower = question.lower()

    # Context-specific empty state messages
    if any(kw in q_lower for kw in ["اليوم", "today"]):
        return {
            "type": "info",
            "text": "لا توجد حركات مسجلة اليوم حتى الآن. جرّب البحث عن أمس أو هذا الأسبوع لعرض آخر النشاطات",
            "icon": "info",
        }
    if any(kw in q_lower for kw in ["مرتجع", "return"]):
        return {
            "type": "positive",
            "text": "لا توجد مرتجعات في هذه الفترة — مؤشر إيجابي على رضا العملاء وجودة المنتجات",
            "icon": "positive",
        }
    if any(kw in q_lower for kw in ["متأخر", "overdue", "مديون"]):
        return {
            "type": "positive",
            "text": "لا توجد مديونيات متأخرة — وضع التحصيل ممتاز",
            "icon": "positive",
        }
    if any(kw in q_lower for kw in ["منخفض", "نفاد", "low", "out of stock"]):
        return {
            "type": "positive",
            "text": "جميع الأصناف بمستويات مخزون كافية — لا توجد أصناف تحت الحد الأدنى",
            "icon": "positive",
        }

    # Domain-specific empty state
    domain_hints = {
        "sales": "جرّب توسيع نطاق التاريخ أو البحث بفرع محدد",
        "inventory": "جرّب البحث بمخزن محدد أو بالاسم الجزئي للصنف",
        "accounting": "تأكد من كود الحساب أو جرّب البحث بالاسم",
        "customers": "جرّب البحث بالاسم الجزئي للعميل",
        "hr": "جرّب توسيع معايير البحث",
    }

    hint = domain_hints.get(domain, "جرّب تعديل معايير البحث أو توسيع نطاق الفترة")
    return {
        "type": "info",
        "text": f"لم يُعثر على نتائج مطابقة — {hint}",
        "icon": "info",
    }


def _single_value_insight(col: str, val: float, domain: str, question: str) -> Optional[dict]:
    """Generate insight for single aggregate value with business context."""
    col_upper = str(col).upper()

    # Sales insights with business reasoning
    if any(kw in col_upper for kw in ["SALES", "FINALTOTAL", "المبيعات"]):
        if val == 0:
            return {
                "type": "warning",
                "text": "لا توجد مبيعات مسجلة في هذه الفترة — تحقق من التاريخ أو الفرع المحدد",
                "icon": "alert",
            }
        elif val > 100000:
            return {
                "type": "positive",
                "text": f"أداء مبيعات قوي تجاوز 100 ألف — مؤشر نشاط تجاري ممتاز",
                "icon": "trending-up",
            }
        elif val > 50000:
            return {
                "type": "positive",
                "text": "معدل مبيعات جيد — أداء ضمن المستوى المستهدف",
                "icon": "trending-up",
            }

    # Count insights
    if any(kw in col_upper for kw in ["COUNT", "عدد"]):
        if val == 0:
            return {
                "type": "info",
                "text": "لا توجد سجلات مطابقة — جرّب توسيع نطاق البحث",
                "icon": "info",
            }
        elif val == 1:
            return {
                "type": "info",
                "text": "نتيجة واحدة فقط — البحث دقيق ومحدد",
                "icon": "info",
            }

    # Balance insights
    if any(kw in col_upper for kw in ["BALANCE", "الرصيد", "OUTSTANDING", "المستحق"]):
        if val < 0:
            return {
                "type": "warning",
                "text": "الرصيد سالب — يشير لوجود التزامات أو مدفوعات تتجاوز المستحقات",
                "icon": "alert",
            }
        elif val > 500000:
            return {
                "type": "warning",
                "text": f"رصيد مرتفع يتجاوز 500 ألف — يستدعي مراجعة وتسوية دورية",
                "icon": "alert",
            }

    return None


def _concentration_insight(col: str, values: list, data: list) -> Optional[dict]:
    """Detect concentration/dominance in data with business reasoning."""
    if not values or sum(values) == 0:
        return None

    total = sum(abs(v) for v in values)
    max_val = max(values)
    if total == 0:
        return None

    top_share = max_val / total * 100

    if top_share >= 40 and len(values) >= 3:
        max_idx = values.index(max_val)
        # Find label column
        label_cols = [c for c in data[0].keys() if isinstance(data[0].get(c), str)]
        top_item = data[max_idx].get(label_cols[0], "") if label_cols else ""

        if top_item:
            if top_share >= 60:
                return {
                    "type": "warning",
                    "text": f"تركّز عالٍ: {top_item} يستحوذ على {top_share:.0f}% من الإجمالي — مخاطر الاعتماد على مصدر واحد تستدعي التنويع",
                    "icon": "alert",
                }
            return {
                "type": "info",
                "text": f"تركّز ملحوظ: {top_item} يمثل {top_share:.0f}% من الإجمالي — يُنصح بمتابعة توزيع المصادر",
                "icon": "info",
            }

    return None


def _trend_insight(col: str, values: list, data: list) -> Optional[dict]:
    """Detect trend direction with business interpretation."""
    if len(values) < 3:
        return None

    # Check if data looks time-ordered
    sample = data[0]
    has_time = any(
        any(kw in str(c).upper() for kw in ["DATE", "MONTH", "الشهر", "التاريخ"])
        for c in sample.keys()
    )
    if not has_time:
        return None

    # Simple trend: compare first half vs second half
    mid = len(values) // 2
    first_half = sum(values[:mid]) / mid if mid > 0 else 0
    second_half = sum(values[mid:]) / (len(values) - mid) if (len(values) - mid) > 0 else 0

    if first_half == 0:
        return None

    change_pct = ((second_half - first_half) / abs(first_half)) * 100

    if change_pct >= 25:
        return {
            "type": "positive",
            "text": f"اتجاه صاعد قوي: نمو {change_pct:.0f}% في النصف الأخير — مسار إيجابي يستحق التعزيز",
            "icon": "trending-up",
        }
    elif change_pct >= 10:
        return {
            "type": "positive",
            "text": f"اتجاه تصاعدي: تحسّن بنسبة {change_pct:.0f}% — أداء مستقر مع نمو تدريجي",
            "icon": "trending-up",
        }
    elif change_pct <= -25:
        return {
            "type": "warning",
            "text": f"تراجع ملحوظ: انخفاض {abs(change_pct):.0f}% في النصف الأخير — يستدعي تحليل الأسباب واتخاذ إجراءات",
            "icon": "trending-down",
        }
    elif change_pct <= -10:
        return {
            "type": "warning",
            "text": f"اتجاه هبوطي: تراجع بنسبة {abs(change_pct):.0f}% — يحتاج مراقبة ومتابعة",
            "icon": "trending-down",
        }

    return None


def _variance_insight(col: str, values: list, data: list) -> Optional[dict]:
    """Detect high variance/inconsistency in data."""
    if len(values) < 4:
        return None

    avg = sum(values) / len(values)
    if avg == 0:
        return None

    # Coefficient of variation
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5
    cv = (std_dev / abs(avg)) * 100

    if cv > 80:
        max_val = max(values)
        min_val = min(values)
        return {
            "type": "info",
            "text": f"تفاوت كبير في القيم: الأعلى {max_val:,.0f} والأدنى {min_val:,.0f} — يشير لعدم انتظام يستحق المراجعة",
            "icon": "variance",
        }

    return None


# ═══════════════════════════════════════════════════════════════════
# Auto-Chart Engine — Intelligent Visualization Selection
# ═══════════════════════════════════════════════════════════════════

def auto_generate_chart(
    data: list,
    question: str = "",
    domain: str = "",
) -> Optional[dict]:
    """Automatically generate chart data when appropriate (no user request needed)."""
    if not data or len(data) < 2 or len(data) > 25:
        return None

    sample = data[0]
    cols = list(sample.keys())

    # Find label and value columns
    label_col = None
    value_cols = []

    for col in cols:
        val = sample.get(col)
        if label_col is None and isinstance(val, str):
            label_col = col
        elif isinstance(val, (int, float)) and val is not None:
            value_cols.append(col)

    if not label_col or not value_cols:
        if len(cols) >= 2:
            label_col = cols[0]
            value_cols = [c for c in cols[1:] if isinstance(sample.get(c), (int, float))]

    if not label_col or not value_cols:
        return None

    # Select chart type
    chart_type = _select_chart_type(data, label_col, value_cols, question)
    val_col = value_cols[0]

    # Build chart
    labels = []
    values = []
    for row in data[:20]:
        lbl = str(row.get(label_col, ""))
        if len(lbl) > 25:
            lbl = lbl[:22] + "..."
        labels.append(lbl)
        v = row.get(val_col, 0)
        values.append(float(v) if v is not None else 0)

    # OKLCH color palette
    colors = [
        "oklch(0.55 0.18 260)",
        "oklch(0.62 0.15 155)",
        "oklch(0.60 0.18 25)",
        "oklch(0.65 0.15 70)",
        "oklch(0.55 0.15 310)",
        "oklch(0.60 0.12 200)",
        "oklch(0.65 0.10 90)",
        "oklch(0.50 0.15 340)",
    ]
    bg_colors = (colors * ((len(labels) // len(colors)) + 1))[:len(labels)]

    # Translate column label
    dataset_label = _COL_CHART_LABELS.get(val_col, _COL_CHART_LABELS.get(val_col.upper(), val_col))

    chart = {
        "type": chart_type,
        "labels": labels,
        "datasets": [{
            "label": dataset_label,
            "data": values,
            "backgroundColor": bg_colors,
        }],
    }

    if chart_type == "line":
        chart["datasets"][0]["borderColor"] = "oklch(0.55 0.18 260)"
        chart["datasets"][0]["fill"] = False
        chart["datasets"][0]["tension"] = 0.35

    return chart


_COL_CHART_LABELS = {
    "total_sales": "إجمالي المبيعات", "TOTAL_SALES": "إجمالي المبيعات",
    "total_debit": "المدين", "TOTAL_DEBIT": "المدين",
    "total_credit": "الدائن", "TOTAL_CREDIT": "الدائن",
    "balance": "الرصيد", "BALANCE": "الرصيد",
    "total_qty": "الكمية", "QTY": "الكمية", "TOTAL_QTY": "الكمية",
    "invoice_count": "عدد الفواتير", "INVOICE_COUNT": "عدد الفواتير",
    "outstanding": "المستحق", "OUTSTANDING": "المستحق",
    "current_qty": "الكمية الحالية",
    "employee_count": "عدد الموظفين", "EMPLOYEE_COUNT": "عدد الموظفين",
    "total_purchases": "إجمالي المشتريات", "TOTAL_PURCHASES": "إجمالي المشتريات",
    "FINALTOTAL": "الإجمالي", "AMOUNT": "المبلغ",
    "المصروفات": "المصروفات", "الايرادات": "الإيرادات", "الصافي": "الصافي",
}


def _select_chart_type(data, label_col, value_cols, question):
    """Select optimal chart type based on data characteristics."""
    label_upper = str(label_col).upper()

    # Time-based → line
    time_keywords = ["DATE", "MONTH", "YEAR", "الشهر", "التاريخ", "VOUCHER_DATE", "INVDATE"]
    if any(kw in label_upper for kw in time_keywords):
        return "line"

    # Question hints
    q_lower = question.lower()
    if any(kw in q_lower for kw in ["نسب", "توزيع", "نسبة", "pie", "دائري"]):
        if len(data) <= 8:
            return "pie"
    if any(kw in q_lower for kw in ["اتجاه", "trend", "شهري", "يومي"]):
        return "line"

    # Data shape
    if len(data) <= 5:
        return "bar"
    elif len(data) <= 15:
        return "bar"

    return "bar"


# ═══════════════════════════════════════════════════════════════════
# Copilot Greeting & Identity
# ═══════════════════════════════════════════════════════════════════

COPILOT_GREETING = """مرحباً! أنا المستشار التنفيذي الذكي لنظام JustClick.

أساعدك في تحليل بيانات شركتك واتخاذ قرارات مبنية على أرقام دقيقة:

- **تحليل المبيعات** — الأداء اليومي، الاتجاهات، المقارنات الذكية
- **إدارة العملاء** — المديونيات، سلوك الدفع، أعلى العملاء
- **المخزون** — الأرصدة الحالية، التنبيهات، حركات المخازن
- **المحاسبة** — كشوف الحسابات، الإيرادات والمصروفات، الأرباح
- **الموظفين** — الإحصائيات، التوزيع، التعيينات الجديدة

اسأل بالعربي أو الإنجليزي — أفهم سياق أعمالك وأقدم تحليلات وتوصيات تنفيذية."""

GREETING_SUGGESTIONS = [
    {"label": "لوحة المبيعات", "query": "لوحة المبيعات", "icon": "dashboard"},
    {"label": "إجمالي المبيعات اليوم", "query": "إجمالي المبيعات اليوم", "icon": "finance"},
    {"label": "أعلى 5 عملاء", "query": "أعلى 5 عملاء في المبيعات", "icon": "ranking"},
    {"label": "الإيرادات والمصروفات", "query": "الإيرادات والمصروفات خلال آخر 6 شهور", "icon": "trend"},
]

COPILOT_HELP = """يمكنني مساعدتك في تحليل واستعراض:

**المبيعات والفواتير**
تفاصيل فاتورة، إجمالي المبيعات، أكثر العملاء شراءً، مقارنات الفترات

**الحسابات المالية**
رصيد حساب، كشف حساب، ميزان المراجعة، الإيرادات والمصروفات

**المخزون والأصناف**
رصيد المخزون، حركات المخزن، الأصناف منخفضة المخزون

**العملاء والموردين**
قائمة العملاء، المديونيات، تحليل سلوك الدفع

**الموظفين**
عدد الموظفين، التوزيع حسب الأقسام، الموظفين الجدد

**اللوحات التحليلية**
لوحة المبيعات، لوحة المخزون، لوحة الموظفين

---
أستطيع أيضاً إنشاء رسوم بيانية، مقارنات، وتحليلات تنفيذية مع توصيات عملية."""
