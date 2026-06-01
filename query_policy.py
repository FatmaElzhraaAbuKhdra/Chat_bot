"""
query_policy.py — Enterprise Query Policy Engine
Replaces blind COMPANY_CODE/FISCAL_YEAR injection with
classification-first, policy-driven filter application.

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │  User Question                                          │
  │       ↓                                                 │
  │  classify_query_scope(question, sql)                    │
  │       ↓                                                 │
  │  PolicyDecision {                                       │
  │    apply_company: bool                                  │
  │    apply_fiscal: bool                                   │
  │    scope: "primary_only" | "all_tenant_tables" | "none" │
  │    reason: str                                          │
  │  }                                                      │
  │       ↓                                                 │
  │  apply_policy(sql, decision)                            │
  │       ↓                                                 │
  │  Filtered SQL (only if policy allows)                   │
  └─────────────────────────────────────────────────────────┘

Query Classifications:
  TRANSACTIONAL — Single-company operational query (invoices, stock, etc.)
    → Apply COMPANY_CODE on primary table, apply FISCAL_YEAR if date-scoped
  ANALYTICAL    — Cross-entity analysis within one company
    → Apply COMPANY_CODE on primary only, NO FISCAL_YEAR (time-series)
  COMPARATIVE   — Multi-company or multi-year comparison
    → NO COMPANY_CODE, NO FISCAL_YEAR (user controls scope)
  AGGREGATION   — Consolidated reports (GROUP BY company/year)
    → NO filters (the whole point is aggregation)
  REFERENCE     — Config/lookup tables (CHARTS, ITEMGROUP, etc.)
    → NO filters (these tables don't have tenant columns)

Design Principles:
  1. NEVER inject if already present
  2. NEVER inject into subqueries
  3. NEVER inject FISCAL_YEAR into time-series/comparison queries
  4. NEVER inject COMPANY_CODE into GROUP BY COMPANY_CODE queries
  5. Primary table gets filter; JOINed children inherit via FK
  6. Independent JOINed tables (CUST, ITEMS) get separate filter
     ONLY if their COMPANY_CODE is not already constrained
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional
from enum import Enum

log = logging.getLogger("query_policy")


# ══════════════════════════════════════════════════════════════════
# Data Model
# ══════════════════════════════════════════════════════════════════

class QueryType(str, Enum):
    TRANSACTIONAL = "transactional"
    ANALYTICAL = "analytical"
    COMPARATIVE = "comparative"
    AGGREGATION = "aggregation"
    REFERENCE = "reference"


class FilterScope(str, Enum):
    PRIMARY_ONLY = "primary_only"       # Filter only the FROM table
    ALL_TENANT = "all_tenant_tables"    # Filter all tenant-aware tables
    NONE = "none"                       # No filters applied


@dataclass
class PolicyDecision:
    """The output of the policy engine — what filters to apply."""
    query_type: QueryType
    apply_company: bool
    apply_fiscal: bool
    scope: FilterScope
    reason: str
    tables_to_filter: list = None    # Specific tables that should receive filters
    tables_to_skip: list = None      # Tables explicitly excluded

    def __post_init__(self):
        if self.tables_to_filter is None:
            self.tables_to_filter = []
        if self.tables_to_skip is None:
            self.tables_to_skip = []


# ══════════════════════════════════════════════════════════════════
# Schema Knowledge
# ══════════════════════════════════════════════════════════════════

# Tables that have COMPANY_CODE column (tenant-isolated)
TENANT_TABLES = {
    "MAIN_INV", "DETAIL_INV", "CUST", "ITEMS", "STORE",
    "TRANSACTION", "TRANSACTION_TOT",
    "VOUCHERS", "VOUCHERS_DET",
    "EMPLOYEES", "EMPLOYEE_SALARIES", "ATT_EMP",
    "EMP_VACATION", "EMP_LOANS", "PAYED", "MAIN_INV_PAYED",
    "ITEM_CARD",
}

# Tables that have FISCAL_YEAR column
FISCAL_TABLES = {
    "MAIN_INV", "DETAIL_INV", "VOUCHERS", "VOUCHERS_DET",
    "TRANSACTION", "TRANSACTION_TOT", "PAYED", "MAIN_INV_PAYED",
}

# Reference/config tables (NEVER get any tenant filter)
REFERENCE_TABLES = {
    "CHARTS", "ITEMGROUP", "UNITS", "COST_CENTERS", "COMPANIES",
    "BRANCHES", "LOOK_UP", "LOOK_UP_PARENT", "CHARTS_ELEMENTS",
    "METHOD_SETUP", "INV_CATEGORIES", "INV_EFFECTS",
    "INV_EFFECTS_RULES", "PRICE_LIST", "SAL_PURCH_TRANS_TYPE",
    "STORE_TRANS_TYPE", "INST",
}

# Parent-child relationships where child inherits tenant from parent via JOIN
# child → parent: if parent is filtered, child doesn't need separate filter
INHERITS_TENANT = {
    "DETAIL_INV": "MAIN_INV",
    "MAIN_INV_PAYED": "MAIN_INV",
    "VOUCHERS_DET": "VOUCHERS",
}


# ══════════════════════════════════════════════════════════════════
# Query Classification Layer
# ══════════════════════════════════════════════════════════════════

def classify_query(sql: str, question: str = "") -> QueryType:
    """
    Classify a query into its business type.
    This determines which policy rules apply.

    Classification hierarchy (first match wins):
      1. REFERENCE — only reference tables used
      2. AGGREGATION — GROUP BY COMPANY_CODE or FISCAL_YEAR
      3. COMPARATIVE — cross-year or cross-company language
      4. ANALYTICAL — time-series, trends, rolling windows
      5. TRANSACTIONAL — default (single-scope operational query)
    """
    sql_upper = sql.upper()
    combined = f"{sql} {question}".lower()

    # ── 1. REFERENCE: Only config tables ──
    tables = _extract_all_tables(sql)
    if tables and tables.issubset(REFERENCE_TABLES | {"DUAL"}):
        return QueryType.REFERENCE

    # ── 2. AGGREGATION: GROUP BY company/fiscal ──
    if re.search(r'GROUP\s+BY[^;]*COMPANY_CODE', sql_upper):
        return QueryType.AGGREGATION
    if re.search(r'GROUP\s+BY[^;]*FISCAL_YEAR', sql_upper):
        return QueryType.AGGREGATION

    # ── 3. COMPARATIVE: Cross-company or cross-year ──
    comparative_signals = [
        # Arabic
        r'مقارنة', r'كل\s*الشركات', r'جميع\s*الشركات', r'بين.*شرك',
        r'مقارنة.*سن[ةو]', r'سنوي', r'سنة\s*\d+.*و.*سنة\s*\d+',
        # English
        r'compare', r'all\s*companies', r'cross.?company',
        r'year\s*over\s*year', r'yoy', r'vs\s*\d{4}',
    ]
    for signal in comparative_signals:
        if re.search(signal, combined, re.IGNORECASE):
            return QueryType.COMPARATIVE

    # SQL-level comparative signals
    if re.search(r'FISCAL_YEAR\s*IN\s*\(', sql_upper):
        return QueryType.COMPARATIVE
    if re.search(r'COMPANY_CODE\s*IN\s*\(', sql_upper):
        return QueryType.COMPARATIVE

    # ── 4. ANALYTICAL: Time-series, trends ──
    analytical_signals = [
        # Date grouping patterns
        r"TO_CHAR\s*\([^)]*'YYYY-MM'",
        r"TO_CHAR\s*\([^)]*'YYYY'",
        r"TRUNC\s*\([^)]*'MM'\s*\)",
        r"TRUNC\s*\([^)]*'YEAR'\s*\)",
        # Arabic time-series
        r'شهري', r'يومي', r'أسبوعي', r'اتجاه', r'ترند', r'تطور',
        r'خلال\s*(آخر|اخر)\s*\d+\s*(شهر|اشهر|أشهر|سنة|سنوات)',
        # English
        r'monthly', r'daily', r'weekly', r'trend', r'over\s*time',
        r'last\s*\d+\s*(months?|years?|weeks?)',
    ]
    for signal in analytical_signals:
        if re.search(signal, combined, re.IGNORECASE):
            return QueryType.ANALYTICAL

    # ── 5. Default: TRANSACTIONAL ──
    return QueryType.TRANSACTIONAL


# ══════════════════════════════════════════════════════════════════
# Policy Decision Engine
# ══════════════════════════════════════════════════════════════════

def decide_policy(
    sql: str,
    question: str = "",
    company_code: str = "",
    fiscal_year: str = "",
) -> PolicyDecision:
    """
    Core policy engine. Decides what filters to apply based on query classification.

    Returns a PolicyDecision that the caller uses to apply (or not apply) filters.
    """
    query_type = classify_query(sql, question)

    # ── REFERENCE queries: never filter ──
    if query_type == QueryType.REFERENCE:
        return PolicyDecision(
            query_type=query_type,
            apply_company=False,
            apply_fiscal=False,
            scope=FilterScope.NONE,
            reason="Reference/config tables only — no tenant columns",
        )

    # ── AGGREGATION queries: never filter (user wants cross-scope) ──
    if query_type == QueryType.AGGREGATION:
        return PolicyDecision(
            query_type=query_type,
            apply_company=False,
            apply_fiscal=False,
            scope=FilterScope.NONE,
            reason="Aggregation across company/year — filters would break report",
        )

    # ── COMPARATIVE queries: never filter ──
    if query_type == QueryType.COMPARATIVE:
        return PolicyDecision(
            query_type=query_type,
            apply_company=False,
            apply_fiscal=False,
            scope=FilterScope.NONE,
            reason="Comparative query — user explicitly comparing across scopes",
        )

    # ── ANALYTICAL queries: company YES, fiscal NO ──
    if query_type == QueryType.ANALYTICAL:
        return PolicyDecision(
            query_type=query_type,
            apply_company=bool(company_code),
            apply_fiscal=False,
            scope=FilterScope.PRIMARY_ONLY,
            reason="Analytical/time-series — company scoped but fiscal-year free for trend analysis",
        )

    # ── TRANSACTIONAL queries: both filters on primary table ──
    return PolicyDecision(
        query_type=query_type,
        apply_company=bool(company_code),
        apply_fiscal=bool(fiscal_year),
        scope=FilterScope.PRIMARY_ONLY,
        reason="Transactional query — single company/year scope",
    )


# ══════════════════════════════════════════════════════════════════
# Filter Application
# ══════════════════════════════════════════════════════════════════

def apply_policy(
    sql: str,
    company_code: str = "",
    fiscal_year: str = "",
    question: str = "",
) -> str:
    """
    Main entry point: Apply the query policy to a SQL statement.
    This REPLACES inject_company_filter() as the single source of truth.

    Returns the SQL with appropriate filters (or unchanged if policy says no).
    """
    if not company_code and not fiscal_year:
        return sql

    # Step 1: Get policy decision
    decision = decide_policy(sql, question, company_code, fiscal_year)

    # Step 2: If no filters needed, return unchanged
    if not decision.apply_company and not decision.apply_fiscal:
        log.info(f"[POLICY] {decision.query_type.value}: no filters applied — {decision.reason}")
        return sql

    # Step 3: Determine which tables to filter
    outer_sql = _strip_subqueries(sql)
    table_aliases = _extract_table_aliases(outer_sql)
    if not table_aliases:
        return sql

    filter_targets = _resolve_filter_targets(table_aliases, sql, decision)

    # Step 4: Build conditions
    conditions = []
    for table_name, alias in filter_targets:
        table_upper = table_name.upper()
        prefix = f"{alias}." if alias else ""

        if decision.apply_company and table_upper in TENANT_TABLES:
            cond = f"{prefix}COMPANY_CODE = {company_code}"
            if not _already_filtered(sql, "COMPANY_CODE", alias):
                conditions.append(cond)

        if decision.apply_fiscal and table_upper in FISCAL_TABLES:
            cond = f"{prefix}FISCAL_YEAR = {fiscal_year}"
            if not _already_filtered(sql, "FISCAL_YEAR", alias):
                conditions.append(cond)

    if not conditions:
        log.info(f"[POLICY] {decision.query_type.value}: filters already present, skipping")
        return sql

    # Step 5: Inject at correct position
    result = _inject_at_correct_position(sql, conditions)
    log.info(f"[POLICY] {decision.query_type.value}: applied {len(conditions)} filter(s) "
             f"on {[t[0] for t in filter_targets]}")
    return result


def _resolve_filter_targets(
    table_aliases: list[tuple[str, str]],
    sql: str,
    decision: PolicyDecision,
) -> list[tuple[str, str]]:
    """Determine exactly which tables receive filters based on policy scope."""

    if decision.scope == FilterScope.NONE:
        return []

    if not table_aliases:
        return []

    primary = table_aliases[0]
    primary_upper = primary[0].upper()

    # PRIMARY_ONLY: filter just the main FROM table
    if decision.scope == FilterScope.PRIMARY_ONLY:
        # Only if it's a tenant table
        if primary_upper in TENANT_TABLES:
            targets = [primary]
        else:
            # Primary is a reference table — find first tenant table in JOINs
            targets = []
            for t, a in table_aliases[1:]:
                if t.upper() in TENANT_TABLES:
                    targets.append((t, a))
                    break

        # Also filter independent JOINed tenant tables that are NOT children
        for t, a in table_aliases[1:]:
            t_upper = t.upper()
            if t_upper in TENANT_TABLES:
                # Skip if child inherits from a filtered parent
                parent = INHERITS_TENANT.get(t_upper)
                if parent and parent == primary_upper:
                    continue
                # Skip if JOIN condition already has COMPANY_CODE
                a_prefix = f"{a}." if a else f"{t}."
                if re.search(rf'{re.escape(a_prefix)}COMPANY_CODE', sql, re.IGNORECASE):
                    continue
                # Skip if same as primary
                if (t, a) == primary:
                    continue
                if (t, a) not in targets:
                    targets.append((t, a))

        return targets

    # ALL_TENANT: filter every tenant table
    return [(t, a) for t, a in table_aliases if t.upper() in TENANT_TABLES]


# ══════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════

def _extract_all_tables(sql: str) -> set[str]:
    """Extract all table names from SQL."""
    tables = set()
    for m in re.finditer(r'\bFROM\s+(\w+)', sql, re.IGNORECASE):
        tables.add(m.group(1).upper())
    for m in re.finditer(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE):
        tables.add(m.group(1).upper())
    # Remove SQL keywords
    tables -= {"SELECT", "WHERE", "AND", "OR", "NOT", "IN", "EXISTS",
               "CASE", "WHEN", "THEN", "ELSE", "END", "NULL"}
    return tables


def _extract_table_aliases(sql: str) -> list[tuple[str, str]]:
    """Extract (table_name, alias) pairs from outer SQL."""
    results = []
    _KEYWORDS = {"WHERE", "ON", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
                 "GROUP", "ORDER", "HAVING", "FETCH", "UNION", "AS",
                 "CROSS", "NATURAL", "FULL", "AND", "OR", "SET"}

    for m in re.finditer(r'\bFROM\s+(\w+)(?:\s+(\w+))?', sql, re.IGNORECASE):
        table = m.group(1)
        alias = m.group(2) or ""
        if alias.upper() in _KEYWORDS:
            alias = ""
        results.append((table, alias))

    for m in re.finditer(r'\bJOIN\s+(\w+)(?:\s+(\w+))?\s+ON', sql, re.IGNORECASE):
        table = m.group(1)
        alias = m.group(2) or ""
        results.append((table, alias))

    return results


def _strip_subqueries(sql: str) -> str:
    """Strip subqueries to analyze only outer-level tables."""
    result = sql
    depth = 0
    parts = []
    start_remove = -1

    for i, ch in enumerate(result):
        if ch == '(' and i + 10 < len(result):
            ahead = result[i+1:i+15].strip().upper()
            if ahead.startswith("SELECT"):
                if depth == 0:
                    start_remove = i
                depth += 1
            elif depth > 0:
                depth += 1
        elif ch == ')' and depth > 0:
            depth -= 1
            if depth == 0:
                parts.append((start_remove, i + 1))

    for start, end in reversed(parts):
        result = result[:start] + "(__SUB__)" + result[end:]
    return result


def _already_filtered(sql: str, column: str, alias: str) -> bool:
    """Check if filter already exists for this column."""
    prefix = f"{alias}." if alias else ""
    patterns = [
        rf'{re.escape(prefix)}{column}\s*(=|IN|BETWEEN)',
        rf'\b{column}\s*(=|IN|BETWEEN)',
    ]
    for p in patterns:
        if re.search(p, sql, re.IGNORECASE):
            return True
    return False


def _inject_at_correct_position(sql: str, conditions: list[str]) -> str:
    """Inject AND conditions at the correct SQL position."""
    cond_str = " AND ".join(conditions)

    end_markers = re.compile(
        r'\b(GROUP\s+BY|ORDER\s+BY|FETCH\s+FIRST|HAVING|UNION)\b',
        re.IGNORECASE
    )

    marker_match = end_markers.search(sql)

    if re.search(r'\bWHERE\b', sql, re.IGNORECASE):
        # WHERE exists — inject before end markers or at end
        if marker_match:
            pos = marker_match.start()
            sql = sql[:pos].rstrip() + f"\n   AND {cond_str}\n" + sql[pos:]
        else:
            sql = sql.rstrip() + f"\n   AND {cond_str}"
    else:
        # No WHERE — create one
        if marker_match:
            pos = marker_match.start()
            sql = sql[:pos].rstrip() + f"\n WHERE {cond_str}\n" + sql[pos:]
        else:
            sql = sql.rstrip() + f"\n WHERE {cond_str}"

    return sql
