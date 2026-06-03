"""
schema_loader.py
يبني schema context من ملف justclick_comments.sql مباشرة —
بيـ parse جمل COMMENT ON TABLE / COMMENT ON COLUMN بدون ما يشغّلها على الـ DB.

يدعم وضعين:
1. get_schema_context() — كل الجداول (للـ startup فقط)
2. get_relevant_schema(question) — جداول مختارة بناءً على السؤال (للـ chat)
"""
import re
import os
import logging
import oracledb
from pathlib import Path
from typing import Optional

log = logging.getLogger("schema")

_table_comments: dict[str, str] = {}
_column_comments: dict[str, dict[str, str]] = {}
_fk_lines: list[str] = []
_full_context: Optional[str] = None

def _get_comments_file() -> Path:
    return Path(__file__).parent / os.getenv("SCHEMA_FILE", "justclick_comments.sql")

# ── Table domain groups ──────────────────────────────────────────────
TABLE_GROUPS = {
    "accounting": ["CHARTS", "VOUCHERS", "VOUCHERS_DET", "COST_CENTERS"],
    "inventory":  ["ITEMS", "ITEMGROUP", "UNITS", "STORE", "TRANSACTION",
                    "TRANSACTION_TOT", "ITEM_CARD", "INV_CATEGORIES",
                    "STORE_TRANS_TYPE"],
    "invoicing":  ["MAIN_INV", "DETAIL_INV", "MAIN_INV_PAYED", "PAYED",
                    "SAL_PURCH_TRANS_TYPE"],
    "customers":  ["CUST", "PRICE_LIST"],
    "hr":         ["EMPLOYEES", "EMPLOYEE_SALARIES", "ATT_EMP", "EMP_LOANS",
                    "EMP_VACATION", "CHARTS_ELEMENTS", "METHOD_SETUP"],
    "system":     ["COMPANIES", "BRANCHES", "LOOK_UP", "LOOK_UP_PARENT"],
}

# Keywords → domain groups (Arabic + English)
DOMAIN_KEYWORDS = {
    "accounting": [
        "حساب", "حسابات", "قيد", "قيود", "مدين", "دائن", "رصيد",
        "ميزان", "كشف", "يومية", "دفتر", "مركز تكلفة",
        "account", "balance", "debit", "credit", "voucher", "journal",
        "chart", "ledger", "statement",
    ],
    "inventory": [
        "صنف", "أصناف", "مخزون", "مخزن", "مخازن", "كارت", "كمية",
        "وحدة", "وحدات", "رصيد مخزن", "حركة مخزن", "جرد",
        "item", "stock", "inventory", "store", "warehouse", "quantity",
        "unit", "card",
    ],
    "invoicing": [
        "فاتورة", "فواتير", "بيع", "شراء", "مبيعات", "مشتريات",
        "مرتجع", "ضريبة", "خصم", "سداد", "تحصيل", "قسط",
        "invoice", "sale", "purchase", "return", "tax", "payment",
        "discount",
    ],
    "customers": [
        "عميل", "عملاء", "مورد", "موردين", "وكيل", "سعر", "أسعار",
        "قائمة أسعار",
        "customer", "supplier", "vendor", "dealer", "price",
    ],
    "hr": [
        "موظف", "موظفين", "راتب", "رواتب", "حضور", "انصراف",
        "إجازة", "إجازات", "سلفة", "سلف", "بند", "بنود",
        "employee", "salary", "attendance", "vacation", "leave", "loan",
    ],
}

# Tables always included (core reference tables)
ALWAYS_INCLUDE = {"COMPANIES", "BRANCHES"}


async def init_schema_context() -> None:
    global _table_comments, _column_comments, _fk_lines, _full_context

    comments_file = _get_comments_file()
    if comments_file.exists():
        sql_text = comments_file.read_text(encoding="utf-8")
        _table_comments, _column_comments = _parse_comments_file(sql_text)
        log.info(f"[SCHEMA] parsed {len(_table_comments)} tables, "
                 f"{sum(len(v) for v in _column_comments.values())} columns from {comments_file.name}")
    else:
        log.warning(f"[SCHEMA] {comments_file.name} not found")

    # Load FK from DB
    try:
        dsn = f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_SID')}"
        conn = oracledb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            dsn=dsn
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT uc.table_name, ucc.column_name,
                       uc2.table_name parent_table, ucc2.column_name parent_col
                  FROM user_constraints uc
                  JOIN user_cons_columns ucc  ON ucc.constraint_name = uc.constraint_name
                  JOIN user_constraints uc2   ON uc2.constraint_name = uc.r_constraint_name
                  JOIN user_cons_columns ucc2 ON ucc2.constraint_name = uc.r_constraint_name
                 WHERE uc.constraint_type = 'R'
                 ORDER BY 1, 2
            """)
            fk_rows = cur.fetchall()
        conn.close()
        if fk_rows:
            _fk_lines = [f" {c}.{cc}→{p}.{pc}" for c, cc, p, pc in fk_rows]
    except Exception as e:
        log.warning(f"[SCHEMA] could not load FK from DB: {e}")

    # Build full context for health check
    _full_context = _build_tables_context(set(_table_comments.keys()))
    log.info(f"[SCHEMA] full context={len(_full_context)} chars")


def get_schema_context() -> str:
    """Full context (for backward compat / health check)."""
    if _full_context is None:
        raise RuntimeError("Schema context not initialized.")
    return _full_context


def get_relevant_schema(question: str) -> str:
    """Build schema context with only relevant tables for the question."""
    if not _table_comments:
        raise RuntimeError("Schema context not initialized.")

    relevant = _select_tables(question)
    ctx = _build_tables_context(relevant)
    log.info(f"[SCHEMA] question matched {len(relevant)} tables, context={len(ctx)} chars")
    return ctx


# ── Internal helpers ────────────────────────────────────────────────

def _parse_comments_file(sql_text: str) -> tuple[dict, dict]:
    table_comments: dict[str, str] = {}
    column_comments: dict[str, dict[str, str]] = {}

    sql_clean = re.sub(r'--[^\n]*', '', sql_text)

    pattern = re.compile(
        r"COMMENT\s+ON\s+(TABLE|COLUMN)\s+([\w\.]+)\s+IS\s+'(.*?)'\s*;",
        re.IGNORECASE | re.DOTALL
    )

    for match in pattern.finditer(sql_clean):
        kind   = match.group(1).upper()
        target = match.group(2).upper()
        text   = match.group(3).strip()
        text   = re.sub(r'\s+', ' ', text).strip()

        if kind == "TABLE":
            table_comments[target] = text
        elif kind == "COLUMN" and "." in target:
            tbl, col = target.split(".", 1)
            column_comments.setdefault(tbl, {})[col] = text

    return table_comments, column_comments


def _col_annotation(desc: str) -> str:
    """Extract only FK, flag values, and warnings from a column description."""
    parts = []

    fk = re.search(r'FK\s*[→→]\s*([\w.]+)', desc)
    if fk:
        parts.append(f"FK→{fk.group(1)}")

    flags = re.findall(r'(\d)\s*=\s*([^,،.]+)', desc)
    if flags and len(flags) <= 6:
        parts.append(' '.join(f"{v}={lbl.strip()}" for v, lbl in flags))

    for warn in re.finditer(r'⚠\s*([^⚠.]+)', desc):
        parts.append(f"⚠{warn.group(1).strip()}")

    return f"({', '.join(parts)})" if parts else ""


def _select_tables(question: str) -> set[str]:
    """Select relevant tables based on question keywords.
    Phase 9: When no domain keywords match, use ontology + learned concepts
    to select minimal relevant tables instead of defaulting to accounting+invoicing.
    """
    q_lower = question.lower()
    matched_groups = set()

    for group, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in q_lower:
                matched_groups.add(group)
                break

    # Phase 9: If no groups matched, try ontology-based table selection
    if not matched_groups:
        matched_groups = _ontology_select_groups(question)

    # Final fallback: if still nothing, use accounting + invoicing (most common)
    if not matched_groups:
        matched_groups = {"accounting", "invoicing"}

    # Collect tables from matched groups
    tables = set(ALWAYS_INCLUDE)
    for group in matched_groups:
        tables.update(TABLE_GROUPS.get(group, []))

    # Also add FK-related tables: if a selected table references another, add it
    all_known = set(_table_comments.keys())
    extra = set()
    for tbl in tables:
        cols = _column_comments.get(tbl, {})
        for col, desc in cols.items():
            fk = re.search(r'FK\s*[→→]\s*(\w+)', desc)
            if fk:
                ref_tbl = fk.group(1).upper()
                if ref_tbl in all_known:
                    extra.add(ref_tbl)
    tables.update(extra)

    return tables & all_known


def _ontology_select_groups(question: str) -> set[str]:
    """Phase 9: Use ontology to determine domain groups when keywords fail.
    Queries ontology nodes for table-domain relationships and learned concepts.
    """
    try:
        from learning.ontology import find_related_tables
        # find_related_tables returns table names from ontology based on question
        ontology_tables = find_related_tables(question)
        if not ontology_tables:
            return set()

        # Map ontology table names back to domain groups
        groups = set()
        for group_name, group_tables in TABLE_GROUPS.items():
            for tbl_name in ontology_tables:
                if tbl_name.upper() in [t.upper() for t in group_tables]:
                    groups.add(group_name)
                    break
        return groups
    except Exception:
        return set()


# Schema-context budget (chars). MAX_PROMPT_CHARS in llm_client.py is 28000;
# the system-prompt template + examples take ~3.5K, so ~16K leaves ample room
# for conversation history. Measured: a full domain group of comments ≈ 2–7.5K,
# so the full Semantic Layer fits comfortably without truncating meaning.
_SCHEMA_CTX_BUDGET = 16000
_COL_DESC_CAP = 160     # per-column cap (median real desc = 47, avg = 58)
_TBL_DESC_CAP = 300     # per-table cap (was 120 — RC2)


def _compact_desc(text: str, cap: int) -> str:
    """Normalize whitespace and cap length on a word boundary. Keeps meaning intact."""
    d = re.sub(r'\s+', ' ', text or '').strip()
    if len(d) > cap:
        d = d[:cap].rsplit(' ', 1)[0].rstrip() + "…"
    return d


def _build_tables_context(tables: set[str]) -> str:
    """Build schema context = Structural + Semantic layers for a set of tables.

    Each column carries its FULL business meaning from justclick_comments.sql
    (whitespace-normalized, capped at _COL_DESC_CAP). FK markers, flag values
    (0=x 1=y) and ⚠ warnings are preserved because they live inline in the comment
    prose — so no separate FK-only extraction is needed (RC1/RC6 fix).

    A running budget (_SCHEMA_CTX_BUDGET) guards against prompt overflow: any table
    that would exceed it degrades to a name-only column list instead of being dropped.
    """
    parts: list[str] = []
    total = 0

    for tbl in sorted(tables):
        if tbl not in _table_comments:
            continue

        tbl_desc = _compact_desc(_table_comments[tbl], _TBL_DESC_CAP)
        header = f"\n{tbl}: {tbl_desc}"

        cols = _column_comments.get(tbl, {})
        col_lines: list[str] = []
        for col, desc in cols.items():
            cdesc = _compact_desc(desc, _COL_DESC_CAP)
            col_lines.append(f"  • {col}: {cdesc}" if cdesc else f"  • {col}")

        block = header + ("\n" + "\n".join(col_lines) if col_lines else "")

        # Budget guard: degrade to name-only columns rather than overflow the prompt
        if total + len(block) > _SCHEMA_CTX_BUDGET and col_lines:
            names = ", ".join(cols.keys())
            block = header + f"\n  [{names}]"

        parts.append(block)
        total += len(block)

    return "\n".join(parts)


async def refresh_schema_context() -> None:
    global _full_context
    await init_schema_context()
    log.info("[SCHEMA] context refreshed")
