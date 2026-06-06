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

# ── Table selection is COMMENT-DRIVEN ────────────────────────────────
# The old TABLE_GROUPS / DOMAIN_KEYWORDS hardcoded maps were removed: relevant
# tables are now chosen by matching the question against each table's COMMENT ON
# TABLE text (see _select_tables_tiered / _get_table_tokens). Adding a new table =
# adding its comment = the system can select it, with no code change here.

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


_MAX_PRIMARY = 12   # cap on comment-matched primary tables (bounds the prompt)

_table_tokens: Optional[dict] = None
_table_tokens_mtime: float = -1.0
_blocked_tables_cache: Optional[set] = None
_blocked_tables_mtime: float = -1.0


def _comment_tokens(text: str) -> set[str]:
    """Normalized Arabic/Latin words (≥3 chars) from a comment string."""
    out: set[str] = set()
    for w in re.findall(r'[؀-ۿA-Za-z]+', text or ''):
        n = _normalize_concept(w)
        if len(n) >= 3:
            out.add(n)
    return out


def _get_table_tokens() -> dict[str, set[str]]:
    """{TABLE: words from its COMMENT ON TABLE text}. Pure projection of comments,
    rebuilt on comment mtime change. A new commented table becomes selectable
    automatically — no TABLE_GROUPS / keyword edits ever needed again.
    """
    global _table_tokens, _table_tokens_mtime
    if _table_tokens is None or _comments_mtime != _table_tokens_mtime:
        _table_tokens = {t: _comment_tokens(d) for t, d in _table_comments.items()}
        _table_tokens_mtime = _comments_mtime
    return _table_tokens


def _get_blocked_tables() -> set[str]:
    """Tables whose TABLE comment says 'لا تستخدم' or 'NEVER USE' — never selected."""
    global _blocked_tables_cache, _blocked_tables_mtime
    if _blocked_tables_cache is None or _comments_mtime != _blocked_tables_mtime:
        _blocked_tables_cache = {
            t for t, d in _table_comments.items()
            if 'لا تستخدم' in (d or '') or 'NEVER USE' in (d or '').upper()
        }
        _blocked_tables_mtime = _comments_mtime
    return _blocked_tables_cache


def _fk_neighbours(primary: set[str], all_known: set[str]) -> set[str]:
    """FK-linked tables of `primary`, BOTH directions, from comment FK markers:
      forward — a primary column's  'FK → X'  pulls X        (unchanged behaviour)
      reverse — any table with      'FK → P'  (P in primary) is pulled
    Reverse is what lets 'أعلى 5 عملاء' (primary=CUST) reach MAIN_INV, whose
    CUST_ID comment carries 'FK → CUST'.
    """
    neigh: set[str] = set()
    for tbl in primary:                                   # forward
        for _col, desc in _column_comments.get(tbl, {}).items():
            m = re.search(r'FK\s*[→→]\s*(\w+)', desc)
            if m and m.group(1).upper() in all_known:
                neigh.add(m.group(1).upper())
    for tbl, cols in _column_comments.items():            # reverse
        if tbl in primary:
            continue
        for _col, desc in cols.items():
            m = re.search(r'FK\s*[→→]\s*(\w+)', desc)
            if m and m.group(1).upper() in primary:
                neigh.add(tbl.upper())
                break
    return neigh


def _select_tables_tiered(question: str) -> tuple[set[str], set[str]]:
    """COMMENT-DRIVEN table selection — no hardcoded groups or keyword lists.

      primary    = ALWAYS_INCLUDE + tables whose COMMENT ON TABLE shares a word with
                   the question (ranked by overlap, capped at _MAX_PRIMARY) → FULL meaning
      referenced = FK neighbours of primary, BOTH directions (capped)        → name-only
      fallback   = no comment match → ALL commented tables name-only (primary stays
                   ALWAYS_INCLUDE only), never hardcoded domain groups

    Tables whose comment says 'لا تستخدم' / 'NEVER USE' are excluded from both tiers.
    """
    all_known = set(_table_comments.keys())
    blocked = _get_blocked_tables()
    idx = _get_table_tokens()

    q_tokens = _comment_tokens(question)

    scored = sorted(
        ((len(q_tokens & toks), t) for t, toks in idx.items()
         if (q_tokens & toks) and t not in blocked),
        reverse=True,
    )
    matched = [t for _, t in scored[:_MAX_PRIMARY]]

    if matched:
        primary = ((set(ALWAYS_INCLUDE) | set(matched)) & all_known) - blocked
        referenced = (_fk_neighbours(primary, all_known) - primary) - blocked
        referenced = set(sorted(referenced)[:_MAX_REFERENCED])
    else:
        # comment-driven fallback: every commented table, name-only (NOT full schema,
        # NOT hardcoded accounting+invoicing). primary stays minimal so the budget
        # guard renders the rest compactly.
        primary = (set(ALWAYS_INCLUDE) & all_known) - blocked
        referenced = all_known - primary - blocked

    return primary, referenced


def _select_tables(question: str) -> set[str]:
    """Select relevant tables (UNION of both tiers) — legacy/back-compat entry point.
    Used by the ontology JOIN-hint loop in pipeline.py; rendering now goes through
    the tiered path in get_relevant_schema().
    """
    primary, referenced = _select_tables_tiered(question)
    return primary | referenced


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


def get_comment_constraints(question: str) -> str:
    """Collect ⚠ warning clauses from the relevant tables' COLUMN comments and return
    them as a list of MANDATORY constraints.

    The ⚠ rules already live in the comments (e.g. MAIN_INV.INVID '⚠ غير فريد عبر انواع
    الفواتير'); the flat schema context delivers them only as inline description, which
    the LLM may treat as prose and ignore. This lifts every ⚠ clause out so the caller
    can inject it as a hard constraint. Comment-only; no new rules are invented here —
    a ⚠ exists iff a comment author wrote it. Returns "" when no warnings apply.
    """
    _maybe_reload_comments()
    if not _column_comments:
        return ""
    if os.getenv("SCHEMA_TIERED", "1") != "0":
        primary, referenced = _select_tables_tiered(question)
        tables = primary | referenced
    else:
        tables = _select_tables(question)

    lines: list[str] = []
    for tbl in sorted(tables):
        for col, desc in _column_comments.get(tbl, {}).items():
            if '⚠' not in desc:
                continue
            for part in desc.split('⚠')[1:]:
                clause = re.sub(r'\s+', ' ', part).strip()
                # keep the warning sentence; drop trailing prose after first '.'
                clause = re.split(r'\.\s', clause, 1)[0].strip().rstrip('.').strip()
                if clause:
                    lines.append(f"- {tbl}.{col}: ⚠ {clause[:200]}")
    return "\n".join(lines)


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
