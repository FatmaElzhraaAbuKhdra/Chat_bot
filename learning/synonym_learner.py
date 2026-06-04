"""
learning/synonym_learner.py — Arabic ERP Terminology Learning
Learns Arabic ERP terminology, spelling variants, and dialect mappings.
Oracle-first with SQLite fallback.
"""
import re
import json
import logging
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.synonyms")

_T = lambda: tbl("synonyms")


# ═══════════════════════════════════════════════════════════════════
# Built-in ERP Synonyms (seed data)
# ═══════════════════════════════════════════════════════════════════

_SEED_SYNONYMS = [
    # Accounting
    ("رصيد", "balance", "accounting", "account_balance"),
    ("كشف حساب", "account_statement", "accounting", "account_statement"),
    ("ميزان مراجعة", "trial_balance", "accounting", "trial_balance"),
    ("شجرة الحسابات", "chart_of_accounts", "accounting", "chart_of_accounts"),
    ("دليل الحسابات", "chart_of_accounts", "accounting", "chart_of_accounts"),
    ("قيد يومية", "journal_entry", "accounting", "journal_entries"),
    ("مدين", "debit", "accounting", None),
    ("دائن", "credit", "accounting", None),
    ("إيرادات", "revenue", "accounting", "revenue_expenses"),
    ("ايرادات", "revenue", "accounting", "revenue_expenses"),
    ("مصروفات", "expenses", "accounting", "revenue_expenses"),
    ("مصاريف", "expenses", "accounting", "revenue_expenses"),
    ("قائمة الدخل", "income_statement", "accounting", "revenue_expenses"),
    # Invoicing
    ("فاتورة", "invoice", "invoicing", "invoice_detail"),
    ("فاتوره", "invoice", "invoicing", "invoice_detail"),
    ("مبيعات", "sales", "invoicing", "sales_summary"),
    ("مشتريات", "purchases", "invoicing", "purchase_summary"),
    ("مرتجع", "return", "invoicing", None),
    ("ضريبة", "tax", "invoicing", None),
    ("سداد", "payment", "invoicing", None),
    ("تحصيل", "collection", "invoicing", None),
    ("مستحق", "outstanding", "invoicing", "outstanding"),
    ("متأخر", "overdue", "invoicing", "outstanding"),
    ("مديونية", "debt", "invoicing", "outstanding"),
    # Inventory
    ("مخزون", "inventory", "inventory", "stock_balance"),
    ("مخزن", "store", "inventory", "stock_balance"),
    ("مخازن", "stores", "inventory", "stock_balance"),
    ("صنف", "item", "inventory", "item_info"),
    ("أصناف", "items", "inventory", "item_info"),
    ("اصناف", "items", "inventory", "item_info"),
    ("كمية", "quantity", "inventory", "stock_balance"),
    ("رصيد مخزن", "stock_balance", "inventory", "stock_balance"),
    ("جرد", "stock_count", "inventory", None),
    # Customers
    ("عميل", "customer", "customers", "customer_info"),
    ("عملاء", "customers", "customers", "customer_list"),
    ("مورد", "supplier", "customers", "supplier_list"),
    ("موردين", "suppliers", "customers", "supplier_list"),
    # HR
    ("موظف", "employee", "hr", "employee_count"),
    ("موظفين", "employees", "hr", "employee_list"),
    ("راتب", "salary", "hr", "salary_info"),
    ("رواتب", "salaries", "hr", "salary_info"),
    ("حضور", "attendance", "hr", "attendance"),
    ("انصراف", "departure", "hr", "attendance"),
    ("إجازة", "leave", "hr", None),
    ("سلفة", "loan", "hr", None),
]


def seed_synonyms() -> int:
    """Load built-in ERP synonyms (run once on init)."""
    count = 0
    with get_conn() as conn:
        for term, canonical, domain, sub_intent in _SEED_SYNONYMS:
            try:
                if is_oracle():
                    conn.execute(f"""
                        MERGE INTO {_T()} t
                        USING (SELECT :1 AS trm, :2 AS can FROM DUAL) s
                        ON (t.TERM = s.trm AND t.CANONICAL = s.can)
                        WHEN NOT MATCHED THEN
                            INSERT (TERM, CANONICAL, DOMAIN, SUB_INTENT,
                                    CONFIDENCE, SOURCE)
                            VALUES (:3, :4, :5, :6, 1.0, 'seed')
                    """, (term, canonical, term, canonical, domain, sub_intent))
                else:
                    conn.execute(f"""
                        INSERT OR IGNORE INTO {_T()}
                            (term, canonical, domain, sub_intent,
                             confidence, source)
                        VALUES (?, ?, ?, ?, 1.0, 'seed')
                    """, (term, canonical, domain, sub_intent))
                count += 1
            except Exception:
                pass
    log.info(f"[LEARNING] Seeded {count} ERP synonyms")
    return count


# ═══════════════════════════════════════════════════════════════════
# Learn New Synonyms
# ═══════════════════════════════════════════════════════════════════

def learn_synonym(
    term: str,
    canonical: str,
    domain: str = "",
    sub_intent: str = "",
    confidence: float = 0.8,
    source: str = "learned",
) -> bool:
    """Add a new synonym mapping."""
    term = _normalize_arabic(term.strip())
    with get_conn() as conn:
        try:
            if is_oracle():
                conn.execute(f"""
                    MERGE INTO {_T()} t
                    USING (SELECT :1 AS trm, :2 AS can FROM DUAL) s
                    ON (t.TERM = s.trm AND t.CANONICAL = s.can)
                    WHEN MATCHED THEN UPDATE SET
                        USAGE_COUNT = t.USAGE_COUNT + 1,
                        CONFIDENCE = GREATEST(t.CONFIDENCE, :3),
                        DOMAIN = COALESCE(NULLIF(:4, ''), t.DOMAIN),
                        SUB_INTENT = COALESCE(NULLIF(:5, ''), t.SUB_INTENT)
                    WHEN NOT MATCHED THEN INSERT
                        (TERM, CANONICAL, DOMAIN, SUB_INTENT, CONFIDENCE, SOURCE)
                    VALUES (:6, :7, :8, :9, :10, :11)
                """, (term, canonical, confidence, domain, sub_intent,
                      term, canonical, domain, sub_intent, confidence, source))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()} (term, canonical, domain, sub_intent,
                                        confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(term, canonical) DO UPDATE SET
                        usage_count = usage_count + 1,
                        confidence = MAX(confidence, ?),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        sub_intent = COALESCE(NULLIF(?, ''), sub_intent)
                """, (term, canonical, domain, sub_intent, confidence, source,
                      confidence, domain, sub_intent))
            return True
        except Exception as e:
            log.warning(f"[LEARNING] Synonym learn failed: {e}")
            return False


def find_synonyms(text: str) -> list[dict]:
    """Find known synonym matches in a text."""
    text_norm = _normalize_arabic(text.lower())
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT TERM, CANONICAL, DOMAIN, SUB_INTENT, CONFIDENCE
                FROM {_T()}
                WHERE :1 LIKE '%' || TERM || '%'
                ORDER BY CONFIDENCE DESC, LENGTH(TERM) DESC
            """, (text_norm,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT term, canonical, domain, sub_intent, confidence
                FROM {_T()}
                WHERE ? LIKE '%' || term || '%'
                ORDER BY confidence DESC, LENGTH(term) DESC
            """, (text_norm,)).fetchall()
        return [dict(r) for r in rows]


def get_canonical(term: str) -> str | None:
    """Get the canonical English term for an Arabic term."""
    term_norm = _normalize_arabic(term.strip())
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT CANONICAL FROM {_T()}
                WHERE TERM = :1 ORDER BY CONFIDENCE DESC
                FETCH FIRST 1 ROW ONLY
            """, (term_norm,)).fetchone()
        else:
            row = conn.execute(f"""
                SELECT canonical FROM {_T()}
                WHERE term = ? ORDER BY confidence DESC LIMIT 1
            """, (term_norm,)).fetchone()
        if row:
            row = dict(row)  # ROW SAFETY: normalize OracleRow/sqlite3.Row
            return row.get("canonical") or row.get("CANONICAL")
        return None


def suggest_intent_from_synonyms(question: str) -> str | None:
    """Try to infer sub_intent from known synonyms in the question."""
    matches = find_synonyms(question)
    intent_scores: dict[str, float] = {}
    for m in matches:
        si = m.get("sub_intent") or m.get("SUB_INTENT")
        conf = m.get("confidence") or m.get("CONFIDENCE", 0)
        if si:
            intent_scores[si] = intent_scores.get(si, 0) + conf
    if intent_scores:
        return max(intent_scores, key=intent_scores.get)
    return None


# ═══════════════════════════════════════════════════════════════════
# Arabic Text Normalization
# ═══════════════════════════════════════════════════════════════════

def _normalize_arabic(text: str) -> str:
    """Normalize Arabic text for matching."""
    text = re.sub(r'[ً-ٰ۟]', '', text)  # tashkeel
    text = re.sub(r'[أإآ]', 'ا', text)                  # alef variants
    text = text.replace('ة', 'ه')                        # taa marbuta
    text = text.replace('ى', 'ي')                        # alef maqsura
    return text


# ═══════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════

def get_synonym_stats() -> dict:
    """Get synonym database statistics."""
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT canonical) AS unique_concepts,
                   COUNT(DISTINCT domain) AS domains,
                   SUM(CASE WHEN source='seed' THEN 1 ELSE 0 END) AS seeded,
                   SUM(CASE WHEN source!='seed' THEN 1 ELSE 0 END) AS learned
            FROM {_T()}
        """).fetchone()
        return dict(row) if row else {}
