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
import threading
import oracledb
from pathlib import Path
from typing import Optional

log = logging.getLogger("schema")

_table_comments: dict[str, str] = {}
_column_comments: dict[str, dict[str, str]] = {}
_fk_lines: list[str] = []
_full_context: Optional[str] = None
_flag_concept_map: Optional[dict] = None   # derived from comments, lazily built
_comments_mtime: float = 0.0               # mtime of last-parsed comments file
_reload_lock = threading.Lock()            # serializes hot-reload swaps

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
    global _table_comments, _column_comments, _fk_lines, _full_context, _flag_concept_map, _comments_mtime
    _flag_concept_map = None   # rebuild from fresh comments

    comments_file = _get_comments_file()
    if comments_file.exists():
        sql_text = comments_file.read_text(encoding="utf-8")
        _table_comments, _column_comments = _parse_comments_file(sql_text)
        try:
            _comments_mtime = comments_file.stat().st_mtime   # baseline for hot-reload
        except OSError:
            _comments_mtime = 0.0
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


def _maybe_reload_comments() -> None:
    """PRIORITY #1: hot-reload justclick_comments.sql when its mtime changes — no
    restart required.

    - Fast path: one stat() per call (~microseconds); returns immediately if unchanged.
    - Atomic: parse + build into LOCALS, then swap globals under a lock with
      `_comments_mtime` set LAST, so any concurrent reader that detects the change
      blocks on the lock and only proceeds once the full cache is in place — never a
      partially-rebuilt cache.
    - Fail-safe: on ANY error (mid-save read, parse failure, 0 tables) the previous
      cache is kept alive, the error is logged, and requests keep being served.
    - Invalidates the downstream caches built from the OLD comments (schema_cache,
      response_cache) so new behaviour appears on the very next request.
    """
    global _table_comments, _column_comments, _full_context, _flag_concept_map, _comments_mtime
    try:
        f = _get_comments_file()
        if not f.exists():
            return
        m = f.stat().st_mtime
        if m == _comments_mtime:
            return  # unchanged
        with _reload_lock:
            if m == _comments_mtime:
                return  # another thread already reloaded
            text = f.read_text(encoding="utf-8")
            new_tc, new_cc = _parse_comments_file(text)
            if not new_tc:
                log.warning("[SCHEMA] hot-reload parsed 0 tables — keeping previous cache")
                return
            # swap comment dicts first so _build_tables_context uses fresh data,
            # then full context, then mtime LAST (gate stays closed until fully built)
            _table_comments = new_tc
            _column_comments = new_cc
            _flag_concept_map = None                       # rebuilt lazily from new comments
            _full_context = _build_tables_context(set(new_tc.keys()))
            _comments_mtime = m
        # downstream caches were built from the OLD comments — drop them
        try:
            from cache import schema_cache
            schema_cache.invalidate()
        except Exception:
            pass
        try:
            import response_cache
            response_cache.invalidate_all()
        except Exception:
            pass
        try:
            import normalizer
            normalizer.invalidate_vocab()
        except Exception:
            pass
        log.info(f"[SCHEMA] comments hot-reloaded ({len(new_tc)} tables) — caches invalidated")
    except Exception as e:
        log.warning(f"[SCHEMA] comment hot-reload failed, keeping previous cache: {e}")


def get_relevant_schema(question: str) -> str:
    """Build schema context with only relevant tables for the question.

    P0/F1: two-tier by default (primary = full meaning, referenced = name-only).
    Set SCHEMA_TIERED=0 to revert to the flat full-context behaviour.
    """
    _maybe_reload_comments()   # PRIORITY #1: pick up comment edits without restart
    if not _table_comments:
        raise RuntimeError("Schema context not initialized.")

    if os.getenv("SCHEMA_TIERED", "1") != "0":
        primary, referenced = _select_tables_tiered(question)
        ctx = _build_tiered_context(primary, referenced)
        log.info(f"[SCHEMA] tiered: {len(primary)} primary + {len(referenced)} referenced, "
                 f"context={len(ctx)} chars")
    else:
        relevant = _select_tables(question)
        ctx = _build_tables_context(relevant)
        log.info(f"[SCHEMA] flat: {len(relevant)} tables, context={len(ctx)} chars")
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


def _select_tables_tiered(question: str) -> tuple[set[str], set[str]]:
    """P0/F1: split relevant tables into two tiers.

      primary    = ALWAYS_INCLUDE + domain-group matches  → FULL column meaning
      referenced = FK neighbours of primary (capped)       → name-only, JOIN-able

    The UNION equals the legacy _select_tables() set (minus the referenced cap),
    so JOIN-ability is preserved while the prompt no longer pays full-description
    cost for every FK-reachable table.
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

    all_known = set(_table_comments.keys())

    # PRIMARY: the query's own domain tables (full semantic detail)
    primary = set(ALWAYS_INCLUDE)
    for group in matched_groups:
        primary.update(TABLE_GROUPS.get(group, []))
    primary &= all_known

    # REFERENCED: FK neighbours of primary tables (name-only, for JOINs)
    referenced: set[str] = set()
    for tbl in primary:
        for col, desc in _column_comments.get(tbl, {}).items():
            fk = re.search(r'FK\s*[→→]\s*(\w+)', desc)
            if fk:
                ref_tbl = fk.group(1).upper()
                if ref_tbl in all_known and ref_tbl not in primary:
                    referenced.add(ref_tbl)
    referenced = set(sorted(referenced)[:_MAX_REFERENCED])

    return primary, referenced


def _select_tables(question: str) -> set[str]:
    """Select relevant tables (UNION of both tiers) — legacy/back-compat entry point.
    Used by the ontology JOIN-hint loop in pipeline.py; rendering now goes through
    the tiered path in get_relevant_schema().
    """
    primary, referenced = _select_tables_tiered(question)
    return primary | referenced


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
_MAX_REFERENCED = 18    # P0/F1: bound FK-referenced (name-only) tables


def _compact_desc(text: str, cap: int) -> str:
    """Normalize whitespace and cap length on a word boundary. Keeps meaning intact."""
    d = re.sub(r'\s+', ' ', text or '').strip()
    if len(d) > cap:
        d = d[:cap].rsplit(' ', 1)[0].rstrip() + "…"
    return d


# ── Comment-derived business concepts (single source of truth) ───────
def _normalize_concept(text: str) -> str:
    """Normalize an Arabic concept label for matching (strip leading ال, alef/ya/ta)."""
    t = re.sub(r'[أإآٱ]', 'ا', (text or '').strip().lower())
    t = t.replace('ة', 'ه').replace('ى', 'ي')
    if t.startswith('ال') and len(t) > 4:
        t = t[2:]
    return t


def get_flag_concept_map() -> dict[str, list[tuple[str, str]]]:
    """Derive {concept_label: [(COLUMN, value), …]} from the 'N=label' flag
    definitions inside column comments.

    The comments are the authority for what each coded value MEANS
    (e.g. INVTYPE 0=بيع 1=شراء), so routing/consistency checks read concepts
    from HERE instead of hardcoded keyword lists. Auto-extends as comments grow.
    Cached after first build (and rebuilt automatically on comment hot-reload).
    """
    _maybe_reload_comments()   # PRIORITY #1: pick up comment edits without restart
    global _flag_concept_map
    if _flag_concept_map is not None:
        return _flag_concept_map

    cmap: dict[str, list[tuple[str, str]]] = {}
    for _tbl, cols in _column_comments.items():
        for col, desc in cols.items():
            # Parse main legend only — stop before any ⚠ warning/aside clause.
            # Stop-chars extended: / strips bilingual "label / English" suffixes;
            # — (—) strips "label — English note" suffixes.
            main_legend = desc.split('⚠')[0]
            flags = re.findall(r'(\d)\s*=\s*([^,،.\d⚠/—]+)', main_legend)
            if not (2 <= len(flags) <= 6):     # only genuine small enum columns
                continue
            for val, label in flags:
                lbl = _normalize_concept(label)
                if len(lbl) < 3:
                    continue
                cmap.setdefault(lbl, []).append((col.upper(), val))
    _flag_concept_map = cmap
    return cmap


def resolve_flag(column: str, label: str):
    """COMMENT-FIRST resolver: return the coded VALUE that the comment assigns to
    `label` for `column` — read ONLY from the comment-derived flag map.

    The template knows the concept label (e.g. بيع); comments own the value (0/1).
    Returns None if the label isn't a comment-defined legend for that column
    (caller treats None as "template ineligible → LLM"). No keyword/synonym list;
    matching is exact after Unicode normalization only.
    """
    norm = _normalize_concept(label)
    col = column.upper()
    for lbl, maps in get_flag_concept_map().items():
        if lbl == norm:
            for c, v in maps:
                if c == col:
                    return v
    return None


def _full_table_block(tbl: str) -> str:
    """Render one table with FULL column business meanings (Semantic Layer)."""
    tbl_desc = _compact_desc(_table_comments[tbl], _TBL_DESC_CAP)
    header = f"\n{tbl}: {tbl_desc}"
    cols = _column_comments.get(tbl, {})
    col_lines = []
    for col, desc in cols.items():
        cdesc = _compact_desc(desc, _COL_DESC_CAP)
        col_lines.append(f"  • {col}: {cdesc}" if cdesc else f"  • {col}")
    return header + ("\n" + "\n".join(col_lines) if col_lines else "")


def _name_only_block(tbl: str) -> str:
    """Render one table as name + purpose + column NAMES only (JOIN-able, compact).

    Used for FK-referenced tables (P0/F1): the LLM still sees the table and its
    column names to build JOINs, without spending tokens on full descriptions.
    """
    tbl_desc = _compact_desc(_table_comments[tbl], 120)
    cols = ", ".join(_column_comments.get(tbl, {}).keys())
    return f"\n{tbl}: {tbl_desc}\n  [{cols}]"


def _build_tables_context(tables: set[str]) -> str:
    """Build schema context = Structural + Semantic layers for a set of tables.

    Each column carries its FULL business meaning from justclick_comments.sql
    (whitespace-normalized, capped at _COL_DESC_CAP). FK markers, flag values
    (0=x 1=y) and ⚠ warnings are preserved because they live inline in the comment
    prose — so no separate FK-only extraction is needed (RC1/RC6 fix).

    A running budget (_SCHEMA_CTX_BUDGET) guards against prompt overflow: any table
    that would exceed it degrades to a name-only column list instead of being dropped.
    (Flat renderer — used for the health-check full context and the legacy path.)
    """
    parts: list[str] = []
    total = 0

    for tbl in sorted(tables):
        if tbl not in _table_comments:
            continue

        block = _full_table_block(tbl)

        # Budget guard: degrade to name-only columns rather than overflow the prompt
        if total + len(block) > _SCHEMA_CTX_BUDGET and tbl in _column_comments:
            names = ", ".join(_column_comments.get(tbl, {}).keys())
            block = f"\n{tbl}: {_compact_desc(_table_comments[tbl], _TBL_DESC_CAP)}\n  [{names}]"

        parts.append(block)
        total += len(block)

    return "\n".join(parts)


def _build_tiered_context(primary: set[str], referenced: set[str]) -> str:
    """P0/F1: two-tier schema context.

    PRIMARY tables (the query's domain) get FULL column meanings and are emitted
    FIRST so the budget never starves the tables the query actually needs (fixes
    the alphabetical-ordering degradation, F4). FK-REFERENCED tables follow as
    compact name-only blocks — enough for the LLM to JOIN, without the token cost
    of full descriptions.
    """
    parts: list[str] = []
    total = 0

    for tbl in sorted(primary):
        if tbl not in _table_comments:
            continue
        block = _full_table_block(tbl)
        # Even a primary degrades only if it alone would blow the whole budget
        if total + len(block) > _SCHEMA_CTX_BUDGET and tbl in _column_comments:
            block = _name_only_block(tbl)
        parts.append(block)
        total += len(block)

    for tbl in sorted(referenced):
        if tbl not in _table_comments:
            continue
        block = _name_only_block(tbl)
        if total + len(block) > _SCHEMA_CTX_BUDGET:
            block = f"\n{tbl}: [{', '.join(_column_comments.get(tbl, {}).keys())}]"
        parts.append(block)
        total += len(block)

    return "\n".join(parts)


async def refresh_schema_context() -> None:
    global _full_context
    await init_schema_context()
    log.info("[SCHEMA] context refreshed")
