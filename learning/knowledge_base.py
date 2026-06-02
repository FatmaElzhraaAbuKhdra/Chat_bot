"""
learning/knowledge_base.py — Persistent ERP Knowledge Memory
Stores learned ERP concepts, business rules, table relationships.
Oracle-first with SQLite fallback.
"""
import json
import logging
import re
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.knowledge")

_T = lambda: tbl("erp_knowledge")


# ═══════════════════════════════════════════════════════════════════
# Seed Knowledge (initial ERP concepts)
# ═══════════════════════════════════════════════════════════════════

_SEED_KNOWLEDGE = [
    {
        "concept": "sales_invoice_flow",
        "description_ar": "دورة فاتورة المبيعات: إنشاء فاتورة (MAIN_INV) → بنود الفاتورة (DETAIL_INV) → السداد (PAYED) → التحصيل",
        "description_en": "Sales invoice flow: create invoice → line items → payment → collection",
        "domain": "invoicing",
        "tables_json": '["MAIN_INV", "DETAIL_INV", "PAYED", "MAIN_INV_PAYED", "CUST"]',
        "terms_ar_json": '["فاتورة", "بيع", "سداد", "تحصيل", "مرتجع"]',
        "terms_en_json": '["invoice", "sale", "payment", "collection", "return"]',
        "sql_patterns": json.dumps([
            "MAIN_INV.INVTYPE: 0=بيع, 1=شراء",
            "MAIN_INV.RETURN_FLAG: 0=عادية, 1=مرتجع",
            "JOIN CUST ON CUSTID = CUST_ID AND CUST_TYPE = CUST_TYPE",
        ]),
    },
    {
        "concept": "accounting_voucher_flow",
        "description_ar": "دورة القيد المحاسبي: إنشاء قيد (VOUCHERS) → تفاصيل مدين/دائن (VOUCHERS_DET) → ربط بالحسابات (CHARTS)",
        "description_en": "Accounting voucher flow: create journal entry → debit/credit details → link to chart of accounts",
        "domain": "accounting",
        "tables_json": '["VOUCHERS", "VOUCHERS_DET", "CHARTS", "COST_CENTERS"]',
        "terms_ar_json": '["قيد", "يومية", "مدين", "دائن", "حساب", "ميزان"]',
        "terms_en_json": '["voucher", "journal", "debit", "credit", "account", "trial balance"]',
        "sql_patterns": json.dumps([
            "JOIN ON (VOUCHER_MONTH, VOUCHER_CODE) — لازم العمودين",
            "AMOUNT > 0 = مدين, AMOUNT < 0 = دائن",
            "CHART_TYPE: 0=ميزانية, 1=قائمة الدخل",
        ]),
    },
    {
        "concept": "inventory_transaction_flow",
        "description_ar": "حركات المخزن: إضافة/صرف (TRANSACTION) → أرصدة إجمالية (TRANSACTION_TOT) → بيانات الصنف (ITEMS)",
        "description_en": "Inventory flow: add/issue → total balances → item master data",
        "domain": "inventory",
        "tables_json": '["TRANSACTION", "TRANSACTION_TOT", "ITEMS", "STORE", "ITEMGROUP"]',
        "terms_ar_json": '["مخزن", "صنف", "كمية", "صرف", "إضافة", "جرد", "كارت صنف"]',
        "terms_en_json": '["store", "item", "quantity", "issue", "receipt", "stock count"]',
        "sql_patterns": json.dumps([
            "TRANSACTION_TOT للأرصدة الإجمالية — أسرع من TRANSACTION",
            "JOIN ITEMS ON ITEMID, JOIN STORE ON STORE_CODE",
            "QTY <> 0 لاستبعاد الأصناف بدون رصيد",
        ]),
    },
    {
        "concept": "hr_employee_flow",
        "description_ar": "بيانات الموظفين: بيانات أساسية (EMPLOYEES) → رواتب (EMPLOYEE_SALARIES) → حضور (ATT_EMP) → إجازات (EMP_VACATION) → سلف (EMP_LOANS)",
        "description_en": "HR flow: master data → salaries → attendance → leaves → loans",
        "domain": "hr",
        "tables_json": '["EMPLOYEES", "EMPLOYEE_SALARIES", "ATT_EMP", "EMP_VACATION", "EMP_LOANS"]',
        "terms_ar_json": '["موظف", "راتب", "حضور", "انصراف", "إجازة", "سلفة"]',
        "terms_en_json": '["employee", "salary", "attendance", "leave", "loan"]',
        "sql_patterns": json.dumps([
            "EMP_ACTIVE = '1' للموظفين النشطين",
            "END_SERVICE_FLG = 'N' للموظفين على رأس العمل",
        ]),
    },
    {
        "concept": "chart_of_accounts_structure",
        "description_ar": "شجرة الحسابات: هرمية عبر PARENT_CHART_CODE. CHART_TYPE=0 ميزانية (أصول/خصوم)، CHART_TYPE=1 قائمة الدخل (إيرادات/مصروفات). CHART_NATURE=0 رئيسي، 1 فرعي",
        "description_en": "Chart of accounts: hierarchical via PARENT_CHART_CODE. Type 0=balance sheet, 1=income statement. Nature 0=main, 1=sub",
        "domain": "accounting",
        "tables_json": '["CHARTS"]',
        "terms_ar_json": '["شجرة الحسابات", "دليل الحسابات", "حساب رئيسي", "حساب فرعي", "ميزانية", "قائمة الدخل"]',
        "terms_en_json": '["chart of accounts", "account tree", "main account", "sub account"]',
        "sql_patterns": json.dumps([
            "DECODE(CHART_TYPE, 0, 'ميزانية', 1, 'قائمة الدخل')",
            "DECODE(CHART_NATURE, 0, 'رئيسي', 1, 'فرعي')",
            "CONNECT BY PRIOR CHART_CODE = PARENT_CHART_CODE للشجرة",
        ]),
    },
    {
        "concept": "multi_company",
        "description_ar": "نظام متعدد الشركات: COMPANY_CODE يفصل بيانات كل شركة. COMPANIES جدول الشركات، BRANCHES الفروع.",
        "description_en": "Multi-tenant: COMPANY_CODE separates data per company.",
        "domain": "system",
        "tables_json": '["COMPANIES", "BRANCHES"]',
        "terms_ar_json": '["شركة", "فرع", "كود الشركة"]',
        "terms_en_json": '["company", "branch", "tenant"]',
        "sql_patterns": json.dumps([
            "COMPANY_CODE في معظم الجداول (MAIN_INV, CUST, EMPLOYEES, ...)",
            "FISCAL_YEAR في الجداول المالية (MAIN_INV, VOUCHERS, ...)",
        ]),
    },
]


def seed_knowledge() -> int:
    """Load built-in ERP knowledge (run once on init)."""
    count = 0
    with get_conn() as conn:
        for k in _SEED_KNOWLEDGE:
            try:
                if is_oracle():
                    conn.execute(f"""
                        MERGE INTO {_T()} t
                        USING (SELECT :1 AS c FROM DUAL) s
                        ON (t.CONCEPT = s.c)
                        WHEN NOT MATCHED THEN INSERT
                            (CONCEPT, DESCRIPTION_AR, DESCRIPTION_EN, DOMAIN,
                             TABLES_JSON, TERMS_AR_JSON, TERMS_EN_JSON,
                             SQL_PATTERNS, SOURCE, CONFIDENCE)
                        VALUES (:2, :3, :4, :5, :6, :7, :8, :9, 'seed', 1.0)
                    """, (k["concept"], k["concept"],
                          k["description_ar"], k["description_en"],
                          k["domain"], k.get("tables_json", "[]"),
                          k.get("terms_ar_json", "[]"),
                          k.get("terms_en_json", "[]"),
                          k.get("sql_patterns", "[]")))
                else:
                    conn.execute(f"""
                        INSERT OR IGNORE INTO {_T()}
                            (concept, description_ar, description_en, domain,
                             tables_json, terms_ar_json, terms_en_json,
                             sql_patterns, source, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'seed', 1.0)
                    """, (k["concept"], k["description_ar"], k["description_en"],
                          k["domain"], k.get("tables_json", "[]"),
                          k.get("terms_ar_json", "[]"),
                          k.get("terms_en_json", "[]"),
                          k.get("sql_patterns", "[]")))
                count += 1
            except Exception:
                pass
    log.info(f"[LEARNING] Seeded {count} ERP knowledge entries")
    return count


# ═══════════════════════════════════════════════════════════════════
# Knowledge CRUD
# ═══════════════════════════════════════════════════════════════════

def add_knowledge(
    concept: str,
    description_ar: str = "",
    description_en: str = "",
    domain: str = "",
    tables: list[str] = None,
    terms_ar: list[str] = None,
    terms_en: list[str] = None,
    sql_patterns: list[str] = None,
    source: str = "learned",
    confidence: float = 0.8,
) -> bool:
    """Add or update an ERP knowledge entry."""
    tables_j = json.dumps(tables or [])
    terms_ar_j = json.dumps(terms_ar or [])
    terms_en_j = json.dumps(terms_en or [])
    patterns_j = json.dumps(sql_patterns or [])

    with get_conn() as conn:
        try:
            if is_oracle():
                # Note: NULLIF doesn't work with CLOB/NCLOB in Oracle.
                # Use CASE WHEN for CLOB columns; DECODE for VARCHAR2.
                conn.execute(f"""
                    MERGE INTO {_T()} t
                    USING (SELECT :concept AS c FROM DUAL) s
                    ON (t.CONCEPT = s.c)
                    WHEN MATCHED THEN UPDATE SET
                        DESCRIPTION_AR = CASE WHEN :desc_ar IS NULL THEN t.DESCRIPTION_AR ELSE :desc_ar2 END,
                        DESCRIPTION_EN = CASE WHEN :desc_en IS NULL THEN t.DESCRIPTION_EN ELSE :desc_en2 END,
                        DOMAIN         = DECODE(:domain, '', t.DOMAIN, NULL, t.DOMAIN, :domain2),
                        TABLES_JSON    = CASE WHEN :tables IS NULL THEN t.TABLES_JSON ELSE :tables2 END,
                        TERMS_AR_JSON  = CASE WHEN :terms_ar IS NULL THEN t.TERMS_AR_JSON ELSE :terms_ar2 END,
                        TERMS_EN_JSON  = CASE WHEN :terms_en IS NULL THEN t.TERMS_EN_JSON ELSE :terms_en2 END,
                        SQL_PATTERNS   = CASE WHEN :patterns IS NULL THEN t.SQL_PATTERNS ELSE :patterns2 END,
                        UPDATED_AT     = SYSTIMESTAMP
                    WHEN NOT MATCHED THEN INSERT
                        (CONCEPT, DESCRIPTION_AR, DESCRIPTION_EN, DOMAIN,
                         TABLES_JSON, TERMS_AR_JSON, TERMS_EN_JSON,
                         SQL_PATTERNS, SOURCE, CONFIDENCE)
                    VALUES (:concept2, :desc_ar3, :desc_en3, :domain3,
                            :tables3, :terms_ar3, :terms_en3, :patterns3,
                            :source, :confidence)
                """, dict(
                    concept=concept,
                    desc_ar=description_ar,   desc_ar2=description_ar,   desc_ar3=description_ar,
                    desc_en=description_en,   desc_en2=description_en,   desc_en3=description_en,
                    domain=domain,            domain2=domain,            domain3=domain,
                    tables=tables_j,          tables2=tables_j,          tables3=tables_j,
                    terms_ar=terms_ar_j,      terms_ar2=terms_ar_j,      terms_ar3=terms_ar_j,
                    terms_en=terms_en_j,      terms_en2=terms_en_j,      terms_en3=terms_en_j,
                    patterns=patterns_j,      patterns2=patterns_j,      patterns3=patterns_j,
                    concept2=concept,
                    source=source,
                    confidence=confidence,
                ))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (concept, description_ar, description_en, domain,
                         tables_json, terms_ar_json, terms_en_json,
                         sql_patterns, source, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(concept) DO UPDATE SET
                        description_ar = COALESCE(NULLIF(?, ''), description_ar),
                        description_en = COALESCE(NULLIF(?, ''), description_en),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        tables_json = COALESCE(NULLIF(?, '[]'), tables_json),
                        terms_ar_json = COALESCE(NULLIF(?, '[]'), terms_ar_json),
                        terms_en_json = COALESCE(NULLIF(?, '[]'), terms_en_json),
                        sql_patterns = COALESCE(NULLIF(?, '[]'), sql_patterns),
                        updated_at = datetime('now')
                """, (concept, description_ar, description_en, domain,
                      tables_j, terms_ar_j, terms_en_j, patterns_j,
                      source, confidence,
                      description_ar, description_en, domain,
                      tables_j, terms_ar_j, terms_en_j, patterns_j))
            return True
        except Exception as e:
            log.warning(f"[LEARNING] Knowledge add failed: {e}")
            return False


def get_knowledge(domain: str = "") -> list[dict]:
    """Get knowledge entries, optionally filtered by domain."""
    with get_conn() as conn:
        if domain:
            if is_oracle():
                rows = conn.execute(
                    f"SELECT * FROM {_T()} WHERE DOMAIN = :1 ORDER BY CONCEPT",
                    (domain,)
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {_T()} WHERE domain = ? ORDER BY concept",
                    (domain,)
                ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM {_T()} ORDER BY DOMAIN, CONCEPT"
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            for key in ("tables_json", "terms_ar_json", "terms_en_json",
                        "sql_patterns", "TABLES_JSON", "TERMS_AR_JSON",
                        "TERMS_EN_JSON", "SQL_PATTERNS"):
                if d.get(key):
                    try:
                        d[key] = json.loads(d[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        return results


def search_knowledge(query: str) -> list[dict]:
    """Search knowledge base by Arabic or English terms."""
    q = f"%{query.lower()}%"
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT * FROM {_T()}
                WHERE LOWER(DESCRIPTION_AR) LIKE :1
                   OR LOWER(DESCRIPTION_EN) LIKE :2
                   OR LOWER(TERMS_AR_JSON) LIKE :3
                   OR LOWER(TERMS_EN_JSON) LIKE :4
                   OR LOWER(CONCEPT) LIKE :5
                ORDER BY CONFIDENCE DESC
            """, (q, q, q, q, q)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT * FROM {_T()}
                WHERE LOWER(description_ar) LIKE ?
                   OR LOWER(description_en) LIKE ?
                   OR LOWER(terms_ar_json) LIKE ?
                   OR LOWER(terms_en_json) LIKE ?
                   OR LOWER(concept) LIKE ?
                ORDER BY confidence DESC
            """, (q, q, q, q, q)).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            for key in ("tables_json", "terms_ar_json", "terms_en_json",
                        "sql_patterns", "TABLES_JSON", "TERMS_AR_JSON",
                        "TERMS_EN_JSON", "SQL_PATTERNS"):
                if d.get(key):
                    try:
                        d[key] = json.loads(d[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        return results


def _extract_tables_from_sql(sql: str) -> list[str]:
    """Extract table names referenced in a SQL statement."""
    # Match tokens after FROM / JOIN keywords (ignores subqueries and aliases)
    pattern = re.compile(
        r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)',
        re.IGNORECASE,
    )
    tables = []
    for m in pattern.finditer(sql):
        t = m.group(1).upper()
        if t not in ("SELECT", "WHERE", "ON", "SET", "INTO", "UPDATE", "VALUES"):
            tables.append(t)
    return list(dict.fromkeys(tables))  # deduplicate, preserve order


def _detect_domain_from_tables(tables: list[str]) -> str:
    """Map a list of table names to the most relevant domain."""
    try:
        from schema_loader import TABLE_GROUPS
    except ImportError:
        return "custom"
    scores: dict[str, int] = {}
    for domain, domain_tables in TABLE_GROUPS.items():
        hits = sum(1 for t in tables if t in domain_tables)
        if hits:
            scores[domain] = hits
    if not scores:
        return "custom"
    return max(scores, key=lambda d: scores[d])


# ═══════════════════════════════════════════════════════════════════
# SQL Deep Analysis — JOIN / Column / Term Extraction
# ═══════════════════════════════════════════════════════════════════

_JOIN_KW = {
    'ON', 'WHERE', 'SET', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL',
    'CROSS', 'JOIN', 'AND', 'OR', 'WHEN', 'THEN', 'ELSE', 'END', 'AS',
    'SELECT', 'FROM', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'ALL', 'BY',
    'WITH', 'INTO', 'VALUES', 'MERGE', 'USING', 'MATCHED', 'INSERT',
    'UPDATE', 'DELETE',
}

_COL_SKIP = {
    'SELECT', 'FROM', 'WHERE', 'AS', 'AND', 'OR', 'NOT', 'NULL', 'ON',
    'SUM', 'COUNT', 'AVG', 'MAX', 'MIN', 'DISTINCT', 'CASE', 'WHEN',
    'THEN', 'ELSE', 'END', 'OVER', 'ORDER', 'BY', 'GROUP', 'HAVING',
    'UNION', 'ALL', 'INTO', 'DECODE', 'NVL', 'TRIM', 'UPPER', 'LOWER',
    'TO_CHAR', 'TO_DATE', 'SUBSTR', 'TRUNC', 'ROUND', 'COALESCE',
    'NULLIF', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS',
    'SET', 'BETWEEN', 'LIKE', 'IN', 'IS', 'EXISTS', 'WITH', 'FETCH',
    'NEXT', 'ROWS', 'ONLY', 'OFFSET', 'PARTITION', 'RANK', 'ROW_NUMBER',
    'DENSE_RANK', 'LAG', 'LEAD', 'CONNECT', 'PRIOR', 'START', 'LEVEL',
    'ROWNUM', 'DUAL', 'EXTRACT', 'YEAR', 'MONTH', 'DAY', 'FROM',
}

# Table name → (Arabic terms, English terms)
_TABLE_TERMS: dict[str, tuple[list, list]] = {
    'MAIN_INV':          (['فاتورة', 'فواتير', 'مبيعات', 'بيع', 'مشتريات', 'إيرادات'],
                          ['invoice', 'sale', 'purchase', 'revenue']),
    'DETAIL_INV':        (['بنود فاتورة', 'تفاصيل فاتورة', 'أصناف مباعة'],
                          ['invoice detail', 'line item', 'sold items']),
    'CUST':              (['عميل', 'عملاء', 'مورد', 'موردين', 'زبون'],
                          ['customer', 'supplier', 'vendor', 'client']),
    'ITEMS':             (['صنف', 'أصناف', 'سلعة', 'منتج', 'بضاعة'],
                          ['item', 'product', 'goods', 'material']),
    'EMPLOYEES':         (['موظف', 'موظفين', 'عامل', 'كادر'],
                          ['employee', 'staff', 'worker', 'personnel']),
    'EMPLOYEE_SALARIES': (['راتب', 'رواتب', 'أجر', 'مرتب'],
                          ['salary', 'payroll', 'wage', 'compensation']),
    'ATT_EMP':           (['حضور', 'انصراف', 'غياب', 'دوام'],
                          ['attendance', 'absence', 'timekeeping']),
    'VOUCHERS':          (['قيد', 'قيود', 'يومية', 'قيد محاسبي'],
                          ['voucher', 'journal entry', 'ledger']),
    'VOUCHERS_DET':      (['تفاصيل قيد', 'بنود قيد', 'مدين', 'دائن'],
                          ['voucher detail', 'debit', 'credit']),
    'CHARTS':            (['حساب', 'حسابات', 'شجرة الحسابات', 'دليل الحسابات'],
                          ['account', 'chart of accounts', 'ledger account']),
    'TRANSACTION_TOT':   (['مخزن', 'رصيد مخزن', 'كمية', 'مخزون'],
                          ['stock', 'inventory balance', 'quantity']),
    'TRANSACTION':       (['حركة مخزن', 'حركات', 'صرف', 'إضافة', 'وارد', 'صادر'],
                          ['inventory transaction', 'movement', 'issue', 'receipt']),
    'PAYED':             (['سداد', 'دفع', 'تحصيل', 'قسط'],
                          ['payment', 'receipt', 'collection', 'installment']),
    'PURCHASE_INV':      (['مشتريات', 'فاتورة شراء', 'توريد'],
                          ['purchase', 'buying', 'supply']),
    'STORE':             (['مخزن', 'مستودع', 'مخازن'],
                          ['store', 'warehouse', 'depot']),
    'COST_CENTERS':      (['مركز تكلفة', 'مراكز تكلفة', 'قسم'],
                          ['cost center', 'department']),
    'ITEMGROUP':         (['مجموعة أصناف', 'فئة', 'تصنيف'],
                          ['item group', 'category', 'classification']),
    'MAIN_INV_PAYED':    (['سداد فاتورة', 'ربط سداد'],
                          ['invoice payment link']),
}


def _extract_joins_from_sql(sql: str) -> list[str]:
    """
    Extract JOIN conditions as 'TABLE1.COL = TABLE2.COL [AND ...]' strings.
    Resolves table aliases back to real table names.
    """
    # Build alias → table map
    alias_map: dict[str, str] = {}
    for m in re.finditer(
        r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_$#]*)\s+([A-Z_][A-Z0-9_]*)\b',
        sql, re.IGNORECASE,
    ):
        tname = m.group(1).upper()
        alias = m.group(2).upper()
        if alias not in _JOIN_KW:
            alias_map[alias] = tname
    # Also self-map bare table names
    for m in re.finditer(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_$#]*)\b', sql, re.IGNORECASE):
        t = m.group(1).upper()
        if t not in alias_map:
            alias_map[t] = t

    def _res(x: str) -> str:
        return alias_map.get(x.upper(), x.upper())

    # Find all table.col = table.col pairs
    eq_matches = list(re.finditer(
        r'([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)\s*=\s*([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)',
        sql, re.IGNORECASE,
    ))
    if not eq_matches:
        return []

    # Group pairs that are within 200 chars of each other (= same ON clause)
    groups: list[list] = [[eq_matches[0]]]
    for m in eq_matches[1:]:
        if m.start() - groups[-1][-1].end() < 200:
            groups[-1].append(m)
        else:
            groups.append([m])

    result = []
    for group in groups:
        parts = []
        for m in group:
            t1, c1, t2, c2 = m.groups()
            parts.append(f"{_res(t1)}.{c1.upper()} = {_res(t2)}.{c2.upper()}")
        join_str = " AND ".join(parts)
        if join_str and join_str not in result:
            result.append(join_str)
    return result


def _extract_columns_from_sql(sql: str) -> list[str]:
    """Extract meaningful column names from table.column references in SQL."""
    cols: set[str] = set()
    for m in re.finditer(
        r'\b[A-Z_][A-Z0-9_]*\.([A-Z_][A-Z0-9_]*)\b', sql, re.IGNORECASE
    ):
        col = m.group(1).upper()
        if col not in _COL_SKIP and len(col) > 1 and not col.isdigit():
            cols.add(col)
    return sorted(cols)[:30]


def _extract_business_terms(
    report_name: str,
    description: str,
    tables: list[str],
) -> tuple[list[str], list[str]]:
    """
    Extract Arabic and English business terms from report metadata + tables.
    Returns (terms_ar, terms_en).
    """
    AR_STOP = {
        'من', 'إلى', 'الى', 'في', 'على', 'عن', 'مع', 'هذا', 'هذه',
        'ذلك', 'تلك', 'التي', 'الذي', 'كل', 'جميع', 'بين', 'حتى',
        'لكل', 'خلال', 'بعد', 'قبل', 'منذ', 'عند', 'أو', 'و', 'ثم',
        'لكن', 'بل', 'لا', 'لم', 'لن', 'هو', 'هي', 'هم', 'نحن',
        'أنا', 'أنت', 'حسب', 'وفق', 'تقرير', 'بيانات', 'قائمة',
        'عرض', 'كشف', 'ال',
    }
    EN_STOP = {
        'the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
        'to', 'from', 'and', 'or', 'not', 'is', 'are', 'was', 'were',
        'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
        'report', 'erp', 'data', 'total', 'all', 'per', 'each',
        'list', 'view', 'show',
    }
    terms_ar: list[str] = []
    terms_en: list[str] = []

    combined = f"{report_name} {description}"
    for w in re.findall(r'[؀-ۿ]+', combined):
        if w not in AR_STOP and len(w) >= 2:
            terms_ar.append(w)
    for w in re.findall(r'[a-zA-Z][a-zA-Z_-]*', combined):
        wl = w.lower()
        if wl not in EN_STOP and len(wl) >= 3:
            terms_en.append(wl)

    for t in tables:
        ar_t, en_t = _TABLE_TERMS.get(t, ([], []))
        terms_ar.extend(ar_t)
        terms_en.extend(en_t)

    seen_ar: set[str] = set()
    seen_en: set[str] = set()
    uniq_ar = [w for w in terms_ar if not (w in seen_ar or seen_ar.add(w))]  # type: ignore[func-returns-value]
    uniq_en = [w for w in terms_en if not (w in seen_en or seen_en.add(w))]  # type: ignore[func-returns-value]
    return uniq_ar[:25], uniq_en[:25]


def _update_ontology_from_joins(
    joins: list[str],
    tables: list[str],
    domain: str,
) -> int:
    """Register newly discovered JOIN relationships in the ontology graph."""
    try:
        from .ontology import add_node, add_edge, Relation
    except ImportError:
        return 0

    known = {t.upper() for t in tables}
    count = 0

    for t in tables:
        add_node(f"tbl:{t}", "table", domain=domain)

    for join_str in joins:
        # Extract every (t1.col = t2.col) pair and create one edge per unique table pair
        eq_pairs = re.findall(
            r'([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)\s*=\s*([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)',
            join_str, re.IGNORECASE,
        )
        seen_pairs: set[frozenset] = set()
        for t1, _c1, t2, _c2 in eq_pairs:
            t1u, t2u = t1.upper(), t2.upper()
            pair = frozenset({t1u, t2u})
            if t1u == t2u or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            if t1u in known and t2u in known:
                ok = add_edge(
                    source=f"tbl:{t1u}",
                    target=f"tbl:{t2u}",
                    relation=Relation.JOINS_TO,
                    weight=0.9,
                    metadata={"join": join_str, "source": "trained_report"},
                )
                if ok:
                    count += 1
    return count


def train_from_query(
    report_name: str,
    description: str,
    sql: str,
    company_code: str = "1",
) -> dict:
    """
    Train the AI from an ERP report.
    Extracts tables, JOIN conditions, column names, and business terms.
    Updates the ontology graph with discovered relationships.
    All extracted knowledge is used at runtime for intent detection,
    context building, and SQL generation.
    """
    try:
        from sql_safety import validate_sql_for_storage
        safety = validate_sql_for_storage(sql)
        if not safety.is_safe:
            return {
                "status": "rejected",
                "knowledge_id": "",
                "message": f"SQL غير آمن: {safety.blocked_reason}",
            }
        clean_sql = safety.sql
    except Exception:
        clean_sql = sql.strip().rstrip(";")

    # ── Structural extraction ──
    tables  = _extract_tables_from_sql(clean_sql)
    joins   = _extract_joins_from_sql(clean_sql)
    columns = _extract_columns_from_sql(clean_sql)
    terms_ar, terms_en = _extract_business_terms(report_name, description, tables)
    domain  = _detect_domain_from_tables(tables)

    # ── Build enriched sql_patterns ──
    # [0] full SQL (reference)
    # [1] JOIN conditions  (if any)
    # [2] Columns used     (if any)
    sql_patterns = [clean_sql]
    if joins:
        sql_patterns.append("# JOINs: " + " | ".join(joins[:4]))
    if columns:
        sql_patterns.append("# Columns: " + ", ".join(columns[:15]))

    concept = f"report_{re.sub(r'[^a-zA-Z0-9_؀-ۿ]', '_', report_name)}"

    ok = add_knowledge(
        concept=concept,
        description_ar=description,
        description_en=f"ERP report: {report_name}",
        domain=domain,
        tables=tables,
        terms_ar=terms_ar,
        terms_en=terms_en,
        sql_patterns=sql_patterns,
        source="trained",
        confidence=0.95,
    )

    # ── Update ontology with discovered JOINs ──
    onto_count = 0
    if ok and joins:
        onto_count = _update_ontology_from_joins(joins, tables, domain)
        log.info(f"[LEARNING] Ontology updated: {onto_count} new edges from '{report_name}'")

    log.info(
        f"[LEARNING] train_from_query '{report_name}': "
        f"tables={tables}, joins={len(joins)}, columns={len(columns)}, "
        f"terms_ar={len(terms_ar)}, terms_en={len(terms_en)}, domain={domain}"
    )

    return {
        "status": "learned" if ok else "failed",
        "knowledge_id": concept,
        "tables_found": tables,
        "joins_found": joins,
        "columns_found": columns[:10],
        "terms_ar": terms_ar[:5],
        "terms_en": terms_en[:5],
        "domain": domain,
        "ontology_updated": onto_count,
        "message": (
            "✅ تم تدريب الـ AI — استُخرجت الجداول والعلاقات والمصطلحات وحُدّث الـ Ontology"
            if ok else "فشل الحفظ"
        ),
    }


def get_knowledge_for_llm(domain: str) -> str:
    """Build a compact knowledge context string for LLM prompts."""
    entries = get_knowledge(domain)
    if not entries:
        return ""
    parts = [f"══ معرفة ERP — {domain} ══"]
    for e in entries[:5]:
        desc = e.get('description_ar') or e.get('DESCRIPTION_AR', '')
        parts.append(f"• {desc}")
        patterns = e.get("sql_patterns") or e.get("SQL_PATTERNS", [])
        if isinstance(patterns, list):
            for p in patterns[:3]:
                parts.append(f"  → {p}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# Smart Search — token-based scoring with Arabic normalization
# ═══════════════════════════════════════════════════════════════════

_AR_SEARCH_STOP = {
    'من', 'إلى', 'الى', 'في', 'على', 'عن', 'مع', 'كل', 'هذا', 'هذه',
    'التي', 'الذي', 'حسب', 'و', 'أو', 'لا', 'ما', 'كم', 'هل', 'بين',
    'عند', 'هو', 'هي', 'هم', 'الى', 'بكم', 'اريد', 'أريد', 'اعطني',
    'أعطني', 'ابحث', 'أبحث', 'عرض', 'بيانات', 'معلومات',
}
_EN_SEARCH_STOP = {
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'is', 'are', 'how',
    'many', 'what', 'which', 'who', 'where', 'when', 'why', 'total',
    'show', 'get', 'find', 'list', 'give', 'me', 'all',
}


def _normalize_ar(text: str) -> str:
    """Normalize Arabic text: remove diacritics, normalize alef/ya/ta."""
    text = re.sub(r'[ً-ٰٟ]', '', text)   # diacritics
    text = re.sub(r'[أإآٱ]', 'ا', text)                  # alef variants
    return text.replace('ة', 'ه').replace('ى', 'ي').lower()


def _tokenize_query(text: str) -> set[str]:
    """Split query into meaningful Arabic + English tokens."""
    normalized = _normalize_ar(text)
    tokens: set[str] = set()
    for t in re.findall(r'[؀-ۿ]+|[a-z]+', normalized):
        if len(t) >= 2 and t not in _AR_SEARCH_STOP and t not in _EN_SEARCH_STOP:
            tokens.add(t)
    return tokens


def search_knowledge_smart(query: str, limit: int = 5) -> list[dict]:
    """
    Token-based knowledge search with Arabic normalization.
    Scores entries by how many query tokens match their text fields.
    Falls back to LIKE search if no tokens extracted.
    Used by pipeline Phase 5 to find similar trained reports.
    """
    if not query.strip():
        return []

    query_tokens = _tokenize_query(query)
    if not query_tokens:
        return search_knowledge(query)

    all_entries = get_knowledge()
    scored: list[tuple[float, dict]] = []

    for entry in all_entries:
        # Collect all searchable text from the entry
        text_parts: list[str] = []
        for key in ('description_ar', 'DESCRIPTION_AR',
                    'description_en', 'DESCRIPTION_EN',
                    'concept', 'CONCEPT'):
            v = entry.get(key, '')
            if v:
                text_parts.append(str(v))

        for key in ('terms_ar_json', 'TERMS_AR_JSON',
                    'terms_en_json', 'TERMS_EN_JSON'):
            v = entry.get(key, '')
            if isinstance(v, list):
                text_parts.extend(str(x) for x in v)
            elif v:
                text_parts.append(str(v))

        entry_text = ' '.join(text_parts)
        if not entry_text.strip():
            continue

        entry_tokens = _tokenize_query(entry_text)
        if not entry_tokens:
            continue

        matches = query_tokens & entry_tokens
        if not matches:
            continue

        # Jaccard-like score: intersect / max(query, entry)
        score = len(matches) / max(len(query_tokens), len(entry_tokens))

        # Boost trained reports over seed knowledge
        concept = entry.get('concept') or entry.get('CONCEPT', '')
        if concept.startswith('report_'):
            score *= 1.3

        scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit] if _ > 0.0]
