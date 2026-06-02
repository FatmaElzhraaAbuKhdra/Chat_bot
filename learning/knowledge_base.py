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
                conn.execute(f"""
                    MERGE INTO {_T()} t
                    USING (SELECT :1 AS c FROM DUAL) s
                    ON (t.CONCEPT = s.c)
                    WHEN MATCHED THEN UPDATE SET
                        DESCRIPTION_AR = COALESCE(NULLIF(:2, ''), t.DESCRIPTION_AR),
                        DESCRIPTION_EN = COALESCE(NULLIF(:3, ''), t.DESCRIPTION_EN),
                        DOMAIN = COALESCE(NULLIF(:4, ''), t.DOMAIN),
                        TABLES_JSON = COALESCE(NULLIF(:5, '[]'), t.TABLES_JSON),
                        TERMS_AR_JSON = COALESCE(NULLIF(:6, '[]'), t.TERMS_AR_JSON),
                        TERMS_EN_JSON = COALESCE(NULLIF(:7, '[]'), t.TERMS_EN_JSON),
                        SQL_PATTERNS = COALESCE(NULLIF(:8, '[]'), t.SQL_PATTERNS),
                        UPDATED_AT = SYSTIMESTAMP
                    WHEN NOT MATCHED THEN INSERT
                        (CONCEPT, DESCRIPTION_AR, DESCRIPTION_EN, DOMAIN,
                         TABLES_JSON, TERMS_AR_JSON, TERMS_EN_JSON,
                         SQL_PATTERNS, SOURCE, CONFIDENCE)
                    VALUES (:9, :10, :11, :12, :13, :14, :15, :16, :17, :18)
                """, (concept,
                      description_ar, description_en, domain,
                      tables_j, terms_ar_j, terms_en_j, patterns_j,
                      concept, description_ar, description_en, domain,
                      tables_j, terms_ar_j, terms_en_j, patterns_j,
                      source, confidence))
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


def train_from_query(
    report_name: str,
    description: str,
    sql: str,
    company_code: str = "1",
) -> dict:
    """
    Store an ERP report's SQL as reference knowledge.
    The AI uses stored SQL patterns when answering similar questions.
    """
    import re as _re
    # Light validation — storage only, not execution
    # (allows UNION ALL, APEX bind variables, Oracle views)
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
        clean_sql = sql.strip().rstrip(";")  # basic cleanup only

    tables = _extract_tables_from_sql(clean_sql)
    domain = _detect_domain_from_tables(tables)
    concept = f"report_{_re.sub(r'[^a-zA-Z0-9_؀-ۿ]', '_', report_name)}"

    ok = add_knowledge(
        concept=concept,
        description_ar=description,
        description_en=f"ERP report: {report_name}",
        domain=domain,
        tables=tables,
        sql_patterns=[clean_sql],
        source="trained",
        confidence=0.95,
    )
    return {
        "status": "learned" if ok else "failed",
        "knowledge_id": concept,
        "tables_found": tables,
        "domain": domain,
        "message": "✅ تم تدريب الـ AI على التقرير — سيستخدمه في الإجابات القادمة" if ok else "فشل الحفظ",
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
