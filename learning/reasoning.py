"""
learning/reasoning.py — Business Reasoning Engine
Transforms natural language queries into structured Reasoning Plans.

Capabilities:
  • Query Decomposition: metric / dimension / filters / time range
  • Business Goal Detection: WHY the user is asking
  • KPI Mapping: automatic formula selection per domain
  • Table + JOIN Planning: which tables and joins are required
  • SQL Validation: post-generation check against the plan
  • Adaptive Learning: record successful plan→SQL executions

Pure rule-based logic — no LLM call, runs in <1ms.
Works entirely on top of existing semantic + ontology layers.
"""
from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field

log = logging.getLogger("learning.reasoning")


# ═══════════════════════════════════════════════════════════════════
# Reasoning Plan Dataclass
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ReasoningPlan:
    """Structured execution plan built from a user question before SQL generation."""

    # Identity
    intent: str = ""
    domain: str = ""

    # Query Decomposition
    metric: str = ""            # Primary KPI name  (e.g. NET_SALES)
    metric_formula: str = ""    # SQL expression    (e.g. SUM(D.QTY * D.PRICE + ...))
    dimension: str = ""         # GROUP BY column   (e.g. CUST_NAME)
    dimension_label: str = ""   # Human label       (e.g. العميل)
    aggregation: str = ""       # SUM / COUNT / RANK / AVG / TREND / NET
    filters: list[str] = field(default_factory=list)    # Implicit WHERE conditions
    time_range: str = ""        # current_month / current_year / custom / ""

    # Business Semantics
    business_goal: str = ""     # Arabic: لماذا يُسأل هذا السؤال
    decision_support: str = ""  # English: what decision it supports

    # Technical Requirements (hints injected to LLM)
    required_tables: list[str] = field(default_factory=list)
    required_joins:  list[str] = field(default_factory=list)
    required_kpis:   list[str] = field(default_factory=list)

    # Metadata
    confidence: float = 0.5
    reasoning_trail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ═══════════════════════════════════════════════════════════════════
# Detection Rules — Aggregation
# ═══════════════════════════════════════════════════════════════════

_RANK_KW   = {'أفضل', 'أعلى', 'أكثر', 'أقل', 'أدنى', 'top', 'best', 'highest',
              'lowest', 'rank', 'ranking', 'رتبة', 'ترتيب'}
_COUNT_KW  = {'عدد', 'كم', 'كم عدد', 'count', 'number of', 'how many', 'عدد الفواتير',
              'عدد الأصناف', 'عدد الموظفين', 'عدد العملاء'}
_AVG_KW    = {'متوسط', 'average', 'avg', 'معدل', 'وسطي'}
_TREND_KW  = {'اتجاه', 'trend', 'شهري', 'سنوي', 'تطور', 'مقارنة بالفترة',
              'monthly', 'yearly', 'quarterly', 'ربع سنوي'}
_SUM_KW    = {'مجموع', 'إجمالي', 'total', 'sum', 'كل', 'جميع', 'مبلغ', 'قيمة'}
_NET_KW    = {'صافي', 'net', 'بعد الخصم', 'بعد المرتجع'}


def _detect_aggregation(question: str) -> str:
    q = question.lower()
    if any(w in q for w in _RANK_KW):   return 'RANK'
    if any(w in q for w in _COUNT_KW):  return 'COUNT'
    if any(w in q for w in _AVG_KW):    return 'AVG'
    if any(w in q for w in _TREND_KW):  return 'TREND'
    if any(w in q for w in _NET_KW):    return 'NET'
    if any(w in q for w in _SUM_KW):    return 'SUM'
    return 'SUM'   # default


# ═══════════════════════════════════════════════════════════════════
# Detection Rules — Dimension (GROUP BY)
# ═══════════════════════════════════════════════════════════════════

_DIM_RULES: list[tuple[list[str], str, str]] = [
    # (keywords, column, label_ar)
    (['حسب العميل', 'بالعميل', 'لكل عميل', 'by customer', 'per customer',
      'عملاء', 'زبون', 'زبائن', 'مورد', 'موردين'],
     'CUST_NAME', 'العميل'),
    (['حسب الصنف', 'بالصنف', 'لكل صنف', 'by item', 'per item',
      'أصناف', 'صنف', 'منتج', 'منتجات', 'سلعة'],
     'ITEM_NAME', 'الصنف'),
    (['حسب المخزن', 'بالمخزن', 'by warehouse', 'by store', 'مخازن'],
     'STORE_NAME', 'المخزن'),
    (['حسب الحساب', 'بالحساب', 'by account', 'حسابات'],
     'CHART_NAME', 'الحساب'),
    (['حسب الموظف', 'بالموظف', 'by employee', 'موظفين'],
     'EMP_NAME', 'الموظف'),
    (['حسب المجموعة', 'بالمجموعة', 'by group', 'مجموعة أصناف'],
     'GRP_NAME', 'المجموعة'),
    (['شهري', 'حسب الشهر', 'بالشهر', 'monthly', 'by month'],
     "TO_CHAR(INV_DATE,'YYYY-MM')", 'الشهر'),
    (['سنوي', 'حسب السنة', 'بالسنة', 'yearly', 'by year', 'annual'],
     'FISCAL_YEAR', 'السنة'),
    (['ربع سنوي', 'quarterly', 'by quarter'],
     "TO_CHAR(INV_DATE,'YYYY-Q')", 'الربع'),
]

_DOMAIN_DIM_DEFAULTS: dict[str, tuple[str, str]] = {
    'invoicing':  ('CUST_NAME',  'العميل'),
    'customers':  ('CUST_NAME',  'العميل'),
    'inventory':  ('ITEM_NAME',  'الصنف'),
    'hr':         ('EMP_NAME',   'الموظف'),
    'accounting': ('CHART_NAME', 'الحساب'),
}


def _detect_dimension(question: str, domain: str) -> tuple[str, str]:
    q = question.lower()
    for keywords, col, label in _DIM_RULES:
        if any(kw in q for kw in keywords):
            return col, label
    return _DOMAIN_DIM_DEFAULTS.get(domain, ('', ''))


# ═══════════════════════════════════════════════════════════════════
# Detection Rules — Metric / KPI
# ═══════════════════════════════════════════════════════════════════

# (domain, keywords) → (kpi_name, formula)
_METRIC_RULES: list[tuple[set[str], set[str], str, str, str]] = [
    # domains, keywords, kpi, formula, label_ar
    ({'invoicing', 'customers'},
     {'صافي مبيعات', 'net sales', 'صافي', 'بدون مرتجع'},
     'NET_SALES',
     'SUM(D.QTY * D.PRICE + D.ADD_VAL - D.SUB_VAL)',
     'صافي المبيعات'),

    ({'invoicing', 'customers'},
     {'عدد فواتير', 'invoice count', 'كم فاتورة', 'عدد الفواتير'},
     'INVOICE_COUNT',
     'COUNT(DISTINCT M.INVID)',
     'عدد الفواتير'),

    ({'invoicing', 'inventory'},
     {'كمية', 'quantity', 'qty', 'كميات'},
     'TOTAL_QTY',
     'SUM(D.QTY)',
     'إجمالي الكمية'),

    ({'invoicing', 'customers'},
     {'مبيعات', 'بيع', 'sale', 'revenue', 'إيراد', 'بيعات'},
     'NET_SALES',
     'SUM(D.QTY * D.PRICE + D.ADD_VAL - D.SUB_VAL)',
     'صافي المبيعات'),

    ({'invoicing', 'customers'},
     {'مشتريات', 'شراء', 'purchase', 'buying', 'توريد'},
     'TOTAL_PURCHASES',
     'SUM(D.QTY * D.PRICE)',
     'إجمالي المشتريات'),

    ({'invoicing'},
     {'سداد', 'تحصيل', 'payment', 'collection', 'دفع'},
     'TOTAL_PAYMENTS',
     'SUM(P.AMOUNT)',
     'إجمالي المدفوعات'),

    ({'inventory'},
     {'رصيد', 'balance', 'كمية مخزون', 'مخزون'},
     'STOCK_QTY',
     'SUM(T.QTY_BALANCE)',
     'رصيد المخزون'),

    ({'inventory'},
     {'قيمة مخزون', 'stock value', 'قيمة'},
     'STOCK_VALUE',
     'SUM(T.QTY_BALANCE * T.UNIT_COST)',
     'قيمة المخزون'),

    ({'accounting'},
     {'مدين', 'debit'},
     'DEBIT',
     'SUM(VD.DEBIT)',
     'إجمالي المدين'),

    ({'accounting'},
     {'دائن', 'credit'},
     'CREDIT',
     'SUM(VD.CREDIT)',
     'إجمالي الدائن'),

    ({'accounting'},
     {'رصيد حساب', 'account balance', 'ميزان', 'رصيد'},
     'BALANCE',
     'SUM(VD.DEBIT) - SUM(VD.CREDIT)',
     'الرصيد'),

    ({'hr'},
     {'راتب', 'رواتب', 'salary', 'payroll', 'أجر'},
     'SALARY_TOTAL',
     'SUM(S.BASIC_SALARY + S.ALLOWANCES)',
     'إجمالي الرواتب'),

    ({'hr'},
     {'عدد موظفين', 'employee count', 'موظفين'},
     'EMPLOYEE_COUNT',
     'COUNT(DISTINCT E.EMP_CODE)',
     'عدد الموظفين'),
]


def _detect_metric(question: str, domain: str) -> tuple[str, str]:
    """Returns (kpi_name, formula). Returns best match or domain default."""
    q = question.lower()
    for domains, keywords, kpi, formula, _ in _METRIC_RULES:
        if domain not in domains and 'all' not in domains:
            continue
        if any(kw in q for kw in keywords):
            return kpi, formula

    # Domain defaults
    _DEFAULTS = {
        'invoicing':  ('NET_SALES',    'SUM(D.QTY * D.PRICE + D.ADD_VAL - D.SUB_VAL)'),
        'customers':  ('NET_SALES',    'SUM(D.QTY * D.PRICE + D.ADD_VAL - D.SUB_VAL)'),
        'inventory':  ('STOCK_QTY',    'SUM(T.QTY_BALANCE)'),
        'accounting': ('BALANCE',      'SUM(VD.DEBIT) - SUM(VD.CREDIT)'),
        'hr':         ('SALARY_TOTAL', 'SUM(S.BASIC_SALARY)'),
    }
    return _DEFAULTS.get(domain, ('TOTAL_AMOUNT', 'SUM(AMOUNT)'))


# ═══════════════════════════════════════════════════════════════════
# Detection Rules — Implicit Filters
# ═══════════════════════════════════════════════════════════════════

def _detect_filters(question: str, domain: str) -> list[str]:
    q = question.lower()
    filters: list[str] = []

    if domain in ('invoicing', 'customers'):
        if any(w in q for w in ['شراء', 'مشتريات', 'purchase', 'توريد']):
            filters.append('M.INVTYPE = 1  /* مشتريات */')
        elif any(w in q for w in ['مرتجع', 'مرتجعات', 'return', 'returned']):
            filters.append('M.RETURN_FLAG = 1  /* مرتجعات */')
        else:
            filters.append('M.INVTYPE = 0     /* مبيعات فقط */')
            filters.append('M.RETURN_FLAG = 0  /* بدون مرتجع */')

    if domain == 'hr':
        if any(w in q for w in ['نشط', 'حالي', 'active', 'على رأس العمل']):
            filters.append("E.EMP_ACTIVE = '1'  /* موظفون نشطون */")
        else:
            filters.append("E.END_SERVICE_FLG = 'N'  /* موظفون على رأس العمل */")

    # Time range detection
    if any(w in q for w in ['هذا الشهر', 'الشهر الحالي', 'this month']):
        filters.append("INV_DATE >= TRUNC(SYSDATE, 'MM')  /* هذا الشهر */")
    elif any(w in q for w in ['الشهر الماضي', 'last month']):
        filters.append("INV_DATE >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)  /* الشهر الماضي */")
    elif any(w in q for w in ['هذه السنة', 'السنة الحالية', 'this year']):
        filters.append('FISCAL_YEAR = :FISCAL_YEAR  /* هذه السنة */')
    elif any(w in q for w in ['الربع', 'quarter']):
        filters.append("INV_DATE >= TRUNC(SYSDATE, 'Q')  /* هذا الربع */")

    return filters


def _detect_time_range(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ['هذا الشهر', 'الشهر الحالي', 'this month']):  return 'current_month'
    if any(w in q for w in ['الشهر الماضي', 'last month']):                return 'last_month'
    if any(w in q for w in ['هذه السنة', 'السنة الحالية', 'this year']):  return 'current_year'
    if any(w in q for w in ['الربع', 'quarter']):                          return 'current_quarter'
    return ''


# ═══════════════════════════════════════════════════════════════════
# Table + JOIN Planner
# ═══════════════════════════════════════════════════════════════════

_DOMAIN_TABLE_PLANS: dict[str, dict] = {
    'invoicing_cust': {
        'tables': ['MAIN_INV', 'CUST', 'DETAIL_INV'],
        'joins': [
            'M.CUSTID = C.CUSTID AND M.CUST_TYPE = C.CUST_TYPE',
            'M.INVID = D.INVID AND M.INVTYPE = D.INVTYPE AND M.RETURN_FLAG = D.RETURN_FLAG',
        ],
    },
    'invoicing_item': {
        'tables': ['MAIN_INV', 'DETAIL_INV', 'ITEMS'],
        'joins': [
            'M.INVID = D.INVID AND M.INVTYPE = D.INVTYPE AND M.RETURN_FLAG = D.RETURN_FLAG',
            'D.ITEMID = I.ITEMID',
        ],
    },
    'invoicing_cust_item': {
        'tables': ['MAIN_INV', 'CUST', 'DETAIL_INV', 'ITEMS'],
        'joins': [
            'M.CUSTID = C.CUSTID AND M.CUST_TYPE = C.CUST_TYPE',
            'M.INVID = D.INVID AND M.INVTYPE = D.INVTYPE AND M.RETURN_FLAG = D.RETURN_FLAG',
            'D.ITEMID = I.ITEMID',
        ],
    },
    'invoicing_payment': {
        'tables': ['MAIN_INV', 'MAIN_INV_PAYED', 'PAYED'],
        'joins': [
            'M.INVID = MP.INVID AND M.INVTYPE = MP.INVTYPE',
            'MP.PAYED_ID = P.PAYED_ID',
        ],
    },
    'inventory_balance': {
        'tables': ['TRANSACTION_TOT', 'ITEMS'],
        'joins': ['T.ITEMID = I.ITEMID'],
    },
    'inventory_movement': {
        'tables': ['TRANSACTION', 'ITEMS', 'STORE'],
        'joins': ['T.ITEMID = I.ITEMID', 'T.STORE_CODE = S.STORE_CODE'],
    },
    'accounting_voucher': {
        'tables': ['VOUCHERS', 'VOUCHERS_DET', 'CHARTS'],
        'joins': [
            'V.VOUCHER_MONTH = VD.VOUCHER_MONTH AND V.VOUCHER_CODE = VD.VOUCHER_CODE',
            'VD.CHART_CODE = C.CHART_CODE',
        ],
    },
    'hr_payroll': {
        'tables': ['EMPLOYEES', 'EMPLOYEE_SALARIES'],
        'joins': ['E.EMP_CODE = S.EMP_CODE'],
    },
    'hr_attendance': {
        'tables': ['EMPLOYEES', 'ATT_EMP'],
        'joins': ['E.EMP_CODE = A.EMP_CODE'],
    },
}


def _select_table_plan(domain: str, dimension_col: str, metric: str) -> tuple[list[str], list[str]]:
    """Choose the best table plan given domain, dimension, and metric."""
    if domain in ('invoicing', 'customers'):
        if metric == 'TOTAL_PAYMENTS':
            return (_DOMAIN_TABLE_PLANS['invoicing_payment']['tables'],
                    _DOMAIN_TABLE_PLANS['invoicing_payment']['joins'])
        if 'ITEM' in dimension_col or metric == 'TOTAL_QTY':
            if 'CUST' in dimension_col:
                p = _DOMAIN_TABLE_PLANS['invoicing_cust_item']
            else:
                p = _DOMAIN_TABLE_PLANS['invoicing_item']
        else:
            p = _DOMAIN_TABLE_PLANS['invoicing_cust']
        return p['tables'], p['joins']

    if domain == 'inventory':
        if metric == 'STOCK_QTY' or 'balance' in metric.lower():
            p = _DOMAIN_TABLE_PLANS['inventory_balance']
        else:
            p = _DOMAIN_TABLE_PLANS['inventory_movement']
        return p['tables'], p['joins']

    if domain == 'accounting':
        p = _DOMAIN_TABLE_PLANS['accounting_voucher']
        return p['tables'], p['joins']

    if domain == 'hr':
        if 'ATT' in metric or 'attend' in metric.lower():
            p = _DOMAIN_TABLE_PLANS['hr_attendance']
        else:
            p = _DOMAIN_TABLE_PLANS['hr_payroll']
        return p['tables'], p['joins']

    return [], []


# ═══════════════════════════════════════════════════════════════════
# Business Goal Detection
# ═══════════════════════════════════════════════════════════════════

_GOAL_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ('sales_analysis',      'RANK'):  (
        'تحديد أكبر العملاء مبيعات لتوجيه القوى البيعية وبناء برامج الولاء',
        'Identify top revenue accounts to optimize sales force and loyalty programs'),
    ('sales_analysis',      'TREND'): (
        'تحليل اتجاهات المبيعات لاتخاذ قرارات التسعير والترويج',
        'Analyze sales trends for pricing and promotion decisions'),
    ('sales_analysis',      'SUM'):   (
        'قياس أداء المبيعات الإجمالي ومقارنته بالأهداف',
        'Measure total sales performance vs targets'),
    ('customer_performance','RANK'):  (
        'تقييم العملاء وتصنيفهم حسب القيمة التجارية لتحديد الحسابات الأكثر ربحية',
        'Rank customers by commercial value to identify most profitable accounts'),
    ('purchasing_analysis', 'RANK'):  (
        'تحديد الموردين الرئيسيين وحجم المشتريات لتفعيل سياسات التفاوض',
        'Identify top suppliers by volume to leverage negotiation policies'),
    ('inventory_movement',  'RANK'):  (
        'رصد الأصناف الأكثر حركة لتحسين خطط الشراء والتخزين',
        'Monitor fast-moving items to optimize purchasing and storage plans'),
    ('inventory_movement',  'SUM'):   (
        'متابعة حركات المخزن لضبط الرصيد وتجنب نقص أو تراكم المخزون',
        'Track inventory movements to maintain optimal stock levels'),
    ('accounting_summary',  'NET'):   (
        'مراجعة أرصدة الحسابات لضمان الدقة المالية وإعداد القوائم المالية',
        'Review account balances for financial accuracy and reporting'),
    ('hr_payroll',          'SUM'):   (
        'تحليل تكاليف الرواتب كنسبة من الإيرادات لتحسين الكفاءة التشغيلية',
        'Analyze payroll costs as % of revenue to improve operational efficiency'),
    ('payment_collection',  'SUM'):   (
        'متابعة تحصيل المستحقات وتحديد التأخيرات في السداد',
        'Monitor receivables collection and identify payment delays'),
}

_GENERIC_GOAL = (
    'الحصول على بيانات دقيقة لدعم القرار التجاري',
    'Obtain accurate data to support informed business decisions',
)


def _detect_business_goal(intent: str, aggregation: str) -> tuple[str, str]:
    key = (intent, aggregation)
    if key in _GOAL_MAP:
        return _GOAL_MAP[key]
    # Try with any aggregation
    for (i, _), goal in _GOAL_MAP.items():
        if i == intent:
            return goal
    return _GENERIC_GOAL


# ═══════════════════════════════════════════════════════════════════
# Core: decompose_query → ReasoningPlan
# ═══════════════════════════════════════════════════════════════════

def decompose_query(
    question:   str,
    intent:     str = "",
    domain:     str = "",
    sub_intent: str = "",
) -> ReasoningPlan:
    """
    Decompose a user question into a structured Reasoning Plan.
    Fast rule-based logic — runs in <1ms, no external calls.
    """
    plan = ReasoningPlan(intent=intent or sub_intent, domain=domain)
    trail: list[str] = []

    # Step 1: Aggregation type
    plan.aggregation = _detect_aggregation(question)
    trail.append(f"aggregation={plan.aggregation}")

    # Step 2: Dimension (GROUP BY)
    dim_col, dim_label = _detect_dimension(question, domain)
    plan.dimension       = dim_col
    plan.dimension_label = dim_label
    if dim_col:
        trail.append(f"dimension={dim_label}({dim_col})")

    # Step 3: Metric + formula
    plan.metric, plan.metric_formula = _detect_metric(question, domain)
    plan.required_kpis = [plan.metric] if plan.metric else []
    trail.append(f"metric={plan.metric}")

    # Step 4: Implicit filters
    plan.filters = _detect_filters(question, domain)
    plan.time_range = _detect_time_range(question)
    if plan.filters:
        trail.append(f"filters={len(plan.filters)}")

    # Step 5: Table + JOIN plan
    plan.required_tables, plan.required_joins = _select_table_plan(
        domain, plan.dimension, plan.metric
    )
    if plan.required_tables:
        trail.append(f"tables={plan.required_tables}")

    # Step 6: Business goal
    plan.business_goal, plan.decision_support = _detect_business_goal(
        plan.intent, plan.aggregation
    )
    trail.append(f"goal={plan.business_goal[:35]}...")

    # Confidence: how many signals detected
    signals = sum([
        bool(plan.metric),
        bool(plan.dimension),
        plan.aggregation not in ('SUM', ''),
        bool(plan.filters),
        bool(plan.required_tables),
        bool(plan.time_range),
    ])
    plan.confidence = round(min(0.45 + signals * 0.09, 0.95), 2)

    plan.reasoning_trail = trail
    return plan


# ═══════════════════════════════════════════════════════════════════
# Context String Builder (for LLM prompt injection)
# ═══════════════════════════════════════════════════════════════════

def plan_to_context_string(plan: ReasoningPlan) -> str:
    """
    Convert a ReasoningPlan to a compact LLM-injectable context string.
    Prepended to extra_context in pipeline for maximum LLM attention.
    Returns '' when plan has no useful information.
    """
    if not plan.metric and not plan.required_tables:
        return ""

    parts = ["== خطة الاستعلام =="]

    if plan.business_goal:
        parts.append(f"الهدف: {plan.business_goal}")

    metric_line = plan.metric
    if plan.metric_formula:
        metric_line += f" = {plan.metric_formula}"
    if metric_line:
        parts.append(f"المقياس: {metric_line}")

    if plan.dimension:
        group_line = f"GROUP BY {plan.dimension}"
        if plan.dimension_label:
            group_line += f" ({plan.dimension_label})"
        if plan.aggregation == 'RANK':
            group_line += " | ORDER BY DESC"
        elif plan.aggregation == 'TREND':
            group_line += " | ORDER BY time ASC"
        parts.append(group_line)

    if plan.filters:
        parts.append("شروط ضمنية: " + " | ".join(plan.filters[:3]))

    if plan.required_tables:
        parts.append(f"جداول: {', '.join(plan.required_tables)}")

    if plan.required_joins:
        for j in plan.required_joins[:2]:
            parts.append(f"JOIN: {j}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# SQL Validation Against Plan
# ═══════════════════════════════════════════════════════════════════

def validate_sql_against_plan(sql: str, plan: ReasoningPlan) -> list[str]:
    """
    Non-blocking validation of generated SQL against the Reasoning Plan.
    Returns a list of warning strings (does NOT raise or block execution).
    Logged by pipeline for observability.
    """
    if not sql or not plan.metric:
        return []

    warnings: list[str] = []
    sql_upper = sql.upper()

    # Check required tables
    for tbl in plan.required_tables:
        if tbl not in sql_upper:
            warnings.append(f"⚠️ جدول '{tbl}' مطلوب في الخطة لكن غير موجود في SQL")

    # Check aggregation type alignment
    if plan.aggregation == 'RANK' and 'ORDER BY' not in sql_upper:
        warnings.append("⚠️ الخطة تتطلب ترتيبًا (ORDER BY) لكنه غير موجود")

    if plan.aggregation in ('SUM', 'NET') and 'SUM(' not in sql_upper:
        warnings.append("⚠️ الخطة تتطلب SUM() لكنه غير موجود")

    if plan.aggregation == 'COUNT' and 'COUNT(' not in sql_upper:
        warnings.append("⚠️ الخطة تتطلب COUNT() لكنه غير موجود")

    # Check GROUP BY when dimension specified
    if plan.dimension and 'GROUP BY' not in sql_upper:
        warnings.append(f"⚠️ الخطة تتطلب GROUP BY لكنه غير موجود")

    # Domain-specific filter checks
    if plan.domain in ('invoicing', 'customers'):
        if plan.filters and 'INVTYPE' not in sql_upper:
            warnings.append("⚠️ شرط INVTYPE مطلوب لتمييز المبيعات من المشتريات")

    return warnings


# ═══════════════════════════════════════════════════════════════════
# Adaptive Learning — Record Successful Plans
# ═══════════════════════════════════════════════════════════════════

def record_successful_plan(
    question: str,
    plan:     ReasoningPlan,
    sql:      str,
    success:  bool = True,
) -> None:
    """
    Persist a successful plan→SQL execution for adaptive learning.
    Stored in AI_LEARNED_PATTERNS (written path) as a structured pattern.
    Future: feed back into _detect_metric / _detect_dimension improvement.
    """
    if not success or not plan.metric:
        return
    try:
        from .store import get_conn, tbl, is_oracle
        _t = tbl("learned_patterns")
        pattern = json.dumps({
            'question':  question[:200],
            'intent':    plan.intent,
            'metric':    plan.metric,
            'dimension': plan.dimension,
            'agg':       plan.aggregation,
            'tables':    plan.required_tables,
            'confidence':plan.confidence,
        }, ensure_ascii=False)

        with get_conn() as conn:
            if is_oracle():
                conn.execute(f"""
                    INSERT INTO {_t}
                        (USER_ID, INTENT_SEQUENCE, PREDICTED_INTENT,
                         CONFIDENCE, SQL_PATTERN, USED_COUNT)
                    VALUES ('reasoning_engine', :1, :2, :3, :4, 1)
                """, (question[:200], plan.intent or 'general',
                      plan.confidence, sql[:1000] if sql else ''))
            else:
                conn.execute(f"""
                    INSERT OR REPLACE INTO {_t}
                        (user_id, intent_sequence, predicted_intent,
                         confidence, sql_pattern, used_count)
                    VALUES ('reasoning_engine', ?, ?, ?, ?, 1)
                """, (question[:200], plan.intent or 'general',
                      plan.confidence, sql[:1000] if sql else ''))
        log.debug(f"[REASONING] Recorded plan: {plan.intent}/{plan.metric}")
    except Exception as e:
        log.debug(f"[REASONING] record_successful_plan: {e}")
