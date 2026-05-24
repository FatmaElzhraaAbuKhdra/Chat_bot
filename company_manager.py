"""
company_manager.py — Multi-Company Support Layer
يدير فلترة البيانات حسب الشركة، التحقق من الصلاحيات،
وحقن COMPANY_CODE/FISCAL_YEAR في SQL تلقائياً.

الجداول التي تحتوي COMPANY_CODE:
  MAIN_INV, DETAIL_INV, CUST, ITEMS, STORE,
  TRANSACTION, TRANSACTION_TOT, VOUCHERS, VOUCHERS_DET,
  EMPLOYEES, EMPLOYEE_SALARIES, ATT_EMP, EMP_VACATION, EMP_LOANS, PAYED

الجداول المستثناة (ليس فيها COMPANY_CODE):
  CHARTS, ITEMGROUP, UNITS, COST_CENTERS, COMPANIES, BRANCHES,
  LOOK_UP, LOOK_UP_PARENT, CHARTS_ELEMENTS, METHOD_SETUP,
  INV_CATEGORIES, INV_EFFECTS, INV_EFFECTS_RULES, PRICE_LIST,
  SAL_PURCH_TRANS_TYPE, STORE_TRANS_TYPE, INST
"""
import re
import logging
from typing import Optional

log = logging.getLogger("company")

# ── الجداول التي فيها COMPANY_CODE ───────────────────────────────
COMPANY_FILTERED_TABLES = {
    "MAIN_INV", "DETAIL_INV", "CUST", "ITEMS", "STORE",
    "TRANSACTION", "TRANSACTION_TOT",
    "VOUCHERS", "VOUCHERS_DET",
    "EMPLOYEES", "EMPLOYEE_SALARIES", "ATT_EMP",
    "EMP_VACATION", "EMP_LOANS", "PAYED", "MAIN_INV_PAYED",
    "ITEM_CARD",
}

# ── الجداول التي فيها FISCAL_YEAR ────────────────────────────────
FISCAL_YEAR_TABLES = {
    "MAIN_INV", "DETAIL_INV", "VOUCHERS", "VOUCHERS_DET",
    "TRANSACTION", "TRANSACTION_TOT", "PAYED", "MAIN_INV_PAYED",
}


def inject_company_filter(
    sql: str,
    company_code: str = "",
    fiscal_year: str = "",
) -> str:
    """
    حقن شروط COMPANY_CODE و FISCAL_YEAR في SQL تلقائياً.
    يعمل على مستوى الجداول: لكل جدول يحتوي COMPANY_CODE
    يضيف الشرط في WHERE clause أو يعدّل الموجود.

    مثال:
      SELECT * FROM MAIN_INV m WHERE m.INVTYPE = 0
      ↓ بعد الحقن (company_code=1, fiscal_year=2024)
      SELECT * FROM MAIN_INV m WHERE m.INVTYPE = 0
        AND m.COMPANY_CODE = 1 AND m.FISCAL_YEAR = 2024
    """
    if not company_code and not fiscal_year:
        return sql

    # استخراج الجداول المستخدمة مع aliases
    table_aliases = _extract_table_aliases(sql)

    conditions = []
    for table_name, alias in table_aliases:
        table_upper = table_name.upper()
        prefix = f"{alias}." if alias else ""

        if company_code and table_upper in COMPANY_FILTERED_TABLES:
            cond = f"{prefix}COMPANY_CODE = {company_code}"
            # تجنب التكرار — لو الشرط موجود أصلاً
            if cond.upper() not in sql.upper() and "COMPANY_CODE" not in _get_existing_conditions(sql, alias):
                conditions.append(cond)

        if fiscal_year and table_upper in FISCAL_YEAR_TABLES:
            cond = f"{prefix}FISCAL_YEAR = {fiscal_year}"
            if cond.upper() not in sql.upper() and "FISCAL_YEAR" not in _get_existing_conditions(sql, alias):
                conditions.append(cond)

    if not conditions:
        return sql

    # حقن الشروط في نهاية WHERE clause (قبل GROUP BY / ORDER BY / FETCH)
    sql = _inject_conditions(sql, conditions)
    log.info(f"[COMPANY] Injected {len(conditions)} company/fiscal filters")
    return sql


def _extract_table_aliases(sql: str) -> list[tuple[str, str]]:
    """
    استخراج أسماء الجداول و aliases من SQL.
    مثال: FROM MAIN_INV m JOIN CUST cu ON ... → [("MAIN_INV", "m"), ("CUST", "cu")]
    """
    results = []

    # FROM table [alias]
    for m in re.finditer(
        r'\bFROM\s+(\w+)(?:\s+(\w+))?', sql, re.IGNORECASE
    ):
        table = m.group(1)
        alias = m.group(2) or ""
        # تجنب keywords
        if alias.upper() in ("WHERE", "ON", "JOIN", "LEFT", "RIGHT", "INNER",
                              "OUTER", "GROUP", "ORDER", "HAVING", "FETCH",
                              "UNION", "AS"):
            alias = ""
        results.append((table, alias))

    # JOIN table [alias] ON
    for m in re.finditer(
        r'\bJOIN\s+(\w+)(?:\s+(\w+))?\s+ON', sql, re.IGNORECASE
    ):
        table = m.group(1)
        alias = m.group(2) or ""
        results.append((table, alias))

    return results


def _get_existing_conditions(sql: str, alias: str) -> str:
    """Get existing WHERE conditions for a table alias."""
    prefix = f"{alias}." if alias else ""
    # Find all conditions mentioning this alias
    pattern = rf'{re.escape(prefix)}\w+'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return " ".join(matches).upper()


def _inject_conditions(sql: str, conditions: list[str]) -> str:
    """
    حقن شروط إضافية في SQL.
    يضيفها بعد WHERE الأخير وقبل GROUP BY / ORDER BY / FETCH.
    """
    cond_str = " AND ".join(conditions)

    # البحث عن مكان الحقن: قبل GROUP BY / ORDER BY / FETCH / UNION
    end_markers = re.compile(
        r'\b(GROUP\s+BY|ORDER\s+BY|FETCH\s+FIRST|HAVING|UNION)\b',
        re.IGNORECASE
    )

    match = end_markers.search(sql)
    if match:
        insert_pos = match.start()
        sql = sql[:insert_pos].rstrip() + f"\n   AND {cond_str}\n " + sql[insert_pos:]
    elif re.search(r'\bWHERE\b', sql, re.IGNORECASE):
        # WHERE موجود بس مفيش GROUP BY / ORDER BY — نضيف في الآخر
        sql = sql.rstrip() + f"\n   AND {cond_str}"
    else:
        # مفيش WHERE أصلاً — نضيف واحد
        if match:
            insert_pos = match.start()
            sql = sql[:insert_pos].rstrip() + f"\n WHERE {cond_str}\n " + sql[insert_pos:]
        else:
            sql = sql.rstrip() + f"\n WHERE {cond_str}"

    return sql


# ══════════════════════════════════════════════════════════════════
# User Company Access Validation
# ══════════════════════════════════════════════════════════════════

# بسيط: كل المستخدمين عندهم access على كل الشركات
# ممكن يتطور لاحقاً ليقرا من جدول ACC_USERS
_COMPANY_ACCESS: dict[str, list[str]] = {}


async def validate_company_access(user_id: str, company_code: str) -> bool:
    """
    تحقق إن المستخدم عنده صلاحية على الشركة.
    حالياً: True دائماً (dev mode).
    لاحقاً: يقرا من ACC_USERS table.
    """
    if not company_code:
        return True

    # Dev mode — allow all
    if user_id not in _COMPANY_ACCESS:
        return True

    return company_code in _COMPANY_ACCESS.get(user_id, [])


async def get_user_companies(user_id: str) -> list[dict]:
    """
    إرجاع قائمة الشركات المتاحة للمستخدم.
    حالياً: يقرا من جدول COMPANIES.
    """
    try:
        from db import execute_query
        data = await execute_query(
            "SELECT COMPANY_CODE, COMPANY_NAME_AR, COMPANY_NAME_EN "
            "FROM COMPANIES ORDER BY COMPANY_CODE "
            "FETCH FIRST 50 ROWS ONLY"
        )
        return data
    except Exception as e:
        log.warning(f"[COMPANY] Could not load companies: {e}")
        return []
