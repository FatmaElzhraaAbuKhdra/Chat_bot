"""
sql_safety.py — SQL Safety Engine
Validates, sanitizes, and audits SQL before execution.
Prevents dangerous operations, enforces row limits, blocks DML.
"""
import re
from dataclasses import dataclass


@dataclass
class SafetyResult:
    is_safe: bool
    sql: str                    # cleaned/modified SQL
    warnings: list[str]
    blocked_reason: str = ""


# ── Blocked patterns ──────────────────────────────────────────────
_DML_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|CALL|BEGIN|DECLARE|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)

_DANGEROUS_PATTERNS = [
    # UNION ALL SELECT — handled separately by _is_union_injection()
    (re.compile(r";\s*\w", re.IGNORECASE), "Multiple SQL statements detected"),
    (re.compile(r"--\s*\w", re.IGNORECASE), "SQL comment injection"),
    (re.compile(r"/\*.*?\*/", re.DOTALL), "Block comment injection"),
    (re.compile(r"\bxp_\w+", re.IGNORECASE), "xp_ system procedure call"),
    (re.compile(r"\bUTL_\w+", re.IGNORECASE), "UTL_ Oracle utility package"),
    (re.compile(r"\bDBMS_\w+", re.IGNORECASE), "DBMS_ Oracle system package"),
    (re.compile(r"\bSYS\.\w+", re.IGNORECASE), "SYS schema access"),
    (re.compile(r"\bDBA_\w+", re.IGNORECASE), "DBA views access"),
    (re.compile(r"\bV\$\w+", re.IGNORECASE), "V$ performance views access"),
]

# ── Allowed tables ────────────────────────────────────────────────
ALLOWED_TABLES = {
    "MAIN_INV", "DETAIL_INV", "CUST", "ITEMS", "ITEMGROUP", "UNITS",
    "STORE", "TRANSACTION", "TRANSACTION_TOT", "ITEM_CARD",
    "CHARTS", "VOUCHERS", "VOUCHERS_DET", "COST_CENTERS",
    "EMPLOYEES", "EMPLOYEE_SALARIES", "ATT_EMP", "EMP_LOANS",
    "EMP_VACATION", "CHARTS_ELEMENTS", "METHOD_SETUP",
    "COMPANIES", "BRANCHES", "LOOK_UP", "LOOK_UP_PARENT",
    "SAL_PURCH_TRANS_TYPE", "INV_CATEGORIES", "INV_EFFECTS",
    "INV_EFFECTS_RULES", "PAYED", "MAIN_INV_PAYED", "INST",
    "PRICE_LIST", "STORE_TRANS_TYPE",
}

# Row limit enforcement
MAX_ROWS = 500
ROW_LIMIT_PATTERN = re.compile(r"FETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY", re.IGNORECASE)


def _is_union_injection(sql: str) -> bool:
    """
    Smart UNION ALL SELECT detection.
    Returns True only if UNION ALL SELECT references tables NOT in ALLOWED_TABLES.
    Dashboard widgets legitimately use UNION ALL with allowed tables.
    """
    if not re.search(r"\bUNION\s+(ALL\s+)?SELECT\b", sql, re.IGNORECASE):
        return False

    # Extract tables from every sub-SELECT after UNION
    union_parts = re.split(r"\bUNION\s+(ALL\s+)?", sql, flags=re.IGNORECASE)
    for part in union_parts:
        if part is None:
            continue
        tables_in_part = set()
        for m in re.finditer(r'\bFROM\s+(\w+)', part, re.IGNORECASE):
            tables_in_part.add(m.group(1).upper())
        for m in re.finditer(r'\bJOIN\s+(\w+)', part, re.IGNORECASE):
            tables_in_part.add(m.group(1).upper())

        # If a UNION part has no FROM (e.g. SELECT 'literal'), allow it
        if not tables_in_part:
            continue

        unknown = tables_in_part - ALLOWED_TABLES
        if unknown:
            return True

    return False


def validate_sql(sql: str) -> SafetyResult:
    """
    Validate SQL for safety before execution.
    Returns SafetyResult with cleaned SQL or blocked reason.
    """
    warnings = []
    cleaned = _clean_sql(sql)

    # ── Block DML ──
    dml_match = _DML_KEYWORDS.search(cleaned)
    if dml_match:
        return SafetyResult(
            is_safe=False,
            sql=cleaned,
            warnings=[],
            blocked_reason=f"DML/DDL operation blocked: {dml_match.group(0).upper()}",
        )

    # ── Block dangerous patterns ──
    for pattern, reason in _DANGEROUS_PATTERNS:
        if pattern.search(cleaned):
            return SafetyResult(
                is_safe=False,
                sql=cleaned,
                warnings=[],
                blocked_reason=reason,
            )

    # ── Smart UNION ALL check ──
    if _is_union_injection(cleaned):
        return SafetyResult(
            is_safe=False,
            sql=cleaned,
            warnings=[],
            blocked_reason="UNION ALL SELECT injection attempt (unknown tables)",
        )

    # ── Verify it's a SELECT ──
    if not cleaned.upper().lstrip().startswith("SELECT"):
        return SafetyResult(
            is_safe=False,
            sql=cleaned,
            warnings=[],
            blocked_reason="Only SELECT queries are allowed",
        )

    # ── Check table whitelist ──
    tables_used = _extract_tables(cleaned)
    unknown_tables = tables_used - ALLOWED_TABLES
    if unknown_tables:
        warnings.append(f"Unknown tables accessed: {', '.join(unknown_tables)}")

    # ── Enforce row limit ──
    cleaned = _enforce_row_limit(cleaned)

    # ── Check for bind variables ──
    bind_vars = re.findall(r':(?!=)([a-zA-Z_]\w*)', cleaned)
    if bind_vars:
        # Replace bind variables with NULL to prevent errors
        for bv in bind_vars:
            cleaned = re.sub(rf':{bv}\b', 'NULL', cleaned)
        warnings.append(f"Bind variables replaced with NULL: {', '.join(bind_vars)}")

    # ── Check SELECT * ──
    if re.search(r"SELECT\s+\*", cleaned, re.IGNORECASE):
        warnings.append("SELECT * detected; prefer named columns")

    # ── AST-level structural validation ──
    try:
        from sql_ast import validate_sql_ast
        ast_result = validate_sql_ast(cleaned)
        if not ast_result.is_valid:
            # AST found critical violations — block the query
            critical = [v for v in ast_result.violations
                        if "CRITICAL" in v or "INJECTION" in v or "TABLE_VIOLATION" in v]
            if critical:
                return SafetyResult(
                    is_safe=False,
                    sql=cleaned,
                    warnings=[],
                    blocked_reason=f"AST validation failed: {critical[0]}",
                )
            # Non-critical AST violations become warnings
            warnings.extend(ast_result.violations)

        # Complexity warning
        if ast_result.complexity_score > 70:
            warnings.append(f"High complexity score: {ast_result.complexity_score}/100")
    except Exception:
        pass  # AST validation failure should not block the query

    return SafetyResult(
        is_safe=True,
        sql=cleaned,
        warnings=warnings,
    )


def validate_sql_for_storage(sql: str) -> SafetyResult:
    """
    Light validation for SQL that will be STORED as a reference pattern (not executed).
    Allows: UNION ALL, Oracle views, APEX bind variables (:P1_ITEM), subqueries.
    Blocks: DDL/DML, dangerous Oracle packages (UTL_, DBMS_, SYS.), xp_ procedures.
    """
    cleaned = sql.strip().rstrip(";").strip()

    # Block DDL / DML
    dml_match = _DML_KEYWORDS.search(cleaned)
    if dml_match:
        return SafetyResult(
            is_safe=False, sql=cleaned, warnings=[],
            blocked_reason=f"DML/DDL غير مسموح: {dml_match.group(0).upper()}",
        )

    # Block truly dangerous Oracle packages only
    _STORAGE_DANGEROUS = [
        (re.compile(r"\bUTL_\w+", re.IGNORECASE),  "UTL_ Oracle utility package"),
        (re.compile(r"\bDBMS_\w+", re.IGNORECASE), "DBMS_ Oracle system package"),
        (re.compile(r"\bSYS\.\w+",  re.IGNORECASE), "SYS schema access"),
        (re.compile(r"\bxp_\w+",    re.IGNORECASE), "xp_ system procedure"),
    ]
    for pattern, reason in _STORAGE_DANGEROUS:
        if pattern.search(cleaned):
            return SafetyResult(
                is_safe=False, sql=cleaned, warnings=[], blocked_reason=reason,
            )

    # Must be a SELECT (allow leading WITH for CTEs)
    first_kw = re.match(r'\s*(SELECT|WITH)\b', cleaned, re.IGNORECASE)
    if not first_kw:
        return SafetyResult(
            is_safe=False, sql=cleaned, warnings=[],
            blocked_reason="يجب أن يبدأ الـ SQL بـ SELECT أو WITH",
        )

    return SafetyResult(is_safe=True, sql=cleaned, warnings=[])


def _clean_sql(sql: str) -> str:
    """Basic SQL cleanup: remove markdown, semicolons, extra whitespace."""
    sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"```\s*", "", sql)
    sql = sql.strip().rstrip(";").strip()
    # Strip bind variables
    sql = re.sub(r':(?!=)([a-zA-Z_]\w*)', 'NULL', sql)
    return sql


# ── Prompt injection detection ───────────────────────────────────
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+.{0,20}(instructions?|rules?|prompts?|constraints?)", re.IGNORECASE),
    re.compile(r"(system\s*prompt|you\s*are\s*now|new\s*instructions?|jailbreak)", re.IGNORECASE),
    re.compile(r"(forget|disregard|override)\s+.{0,15}(everything|all|instructions|rules)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?(different|new|admin|root|hacker)", re.IGNORECASE),
    re.compile(r"(reveal|show|display|output|print)\s+.{0,10}(prompt|instructions|system|password)", re.IGNORECASE),
    re.compile(r"(do\s+not|don.?t)\s+follow\s+.{0,15}(rules|instructions|guidelines)", re.IGNORECASE),
]


def detect_prompt_injection(question: str) -> str:
    """Detect prompt injection attempts in user input.
    Returns empty string if safe, or the detected pattern name.
    """
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(question):
            return pattern.pattern[:50]
    return ""


# ── Query complexity guard ───────────────────────────────────────
MAX_JOINS = 6
MAX_SUBQUERIES = 3
MAX_SQL_LENGTH = 3000


def check_query_complexity(sql: str) -> list[str]:
    """Check if a query is too complex (potential DoS or runaway query).
    Returns list of warnings.
    """
    warnings = []
    # Count JOINs
    join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
    if join_count > MAX_JOINS:
        warnings.append(f"Too many JOINs ({join_count} > {MAX_JOINS})")

    # Count subqueries
    subquery_count = sql.upper().count("SELECT") - 1
    if subquery_count > MAX_SUBQUERIES:
        warnings.append(f"Too many subqueries ({subquery_count} > {MAX_SUBQUERIES})")

    # SQL length
    if len(sql) > MAX_SQL_LENGTH:
        warnings.append(f"SQL too long ({len(sql)} > {MAX_SQL_LENGTH} chars)")

    # Cartesian product detection (FROM with multiple tables, no JOIN/WHERE)
    if re.search(r'FROM\s+\w+\s*,\s*\w+', sql, re.IGNORECASE):
        if not re.search(r'\bWHERE\b', sql, re.IGNORECASE):
            warnings.append("Possible cartesian product (multiple tables without WHERE)")

    return warnings


def _extract_tables(sql: str) -> set[str]:
    """Extract table names from SQL (best effort)."""
    tables = set()
    # FROM clause
    for match in re.finditer(r'\bFROM\s+(\w+)', sql, re.IGNORECASE):
        tables.add(match.group(1).upper())
    # JOIN clause
    for match in re.finditer(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE):
        tables.add(match.group(1).upper())
    return tables


def _enforce_row_limit(sql: str) -> str:
    """Ensure FETCH FIRST N ROWS ONLY is present and within limits."""
    match = ROW_LIMIT_PATTERN.search(sql)
    if match:
        n = int(match.group(1))
        if n > MAX_ROWS:
            sql = ROW_LIMIT_PATTERN.sub(f"FETCH FIRST {MAX_ROWS} ROWS ONLY", sql)
    else:
        # Add row limit if not present
        sql = sql.rstrip()
        sql += f"\nFETCH FIRST {MAX_ROWS} ROWS ONLY"
    return sql


# ── Audit logging ─────────────────────────────────────────────────
_audit_log: list[dict] = []
MAX_AUDIT = 1000


def log_query(user: str, question: str, sql: str, safety: SafetyResult,
              success: bool, rows: int = 0, error: str = ""):
    """Log a query execution for audit purposes."""
    import time
    entry = {
        "timestamp": time.time(),
        "user": user,
        "question": question[:200],
        "sql": sql[:500],
        "is_safe": safety.is_safe,
        "blocked_reason": safety.blocked_reason,
        "warnings": safety.warnings,
        "success": success,
        "rows": rows,
        "error": error[:200],
    }
    _audit_log.append(entry)
    if len(_audit_log) > MAX_AUDIT:
        _audit_log.pop(0)


def get_audit_log(limit: int = 50) -> list[dict]:
    """Return recent audit entries."""
    return _audit_log[-limit:]


def get_audit_stats() -> dict:
    """Return aggregate audit statistics."""
    if not _audit_log:
        return {"total": 0, "success": 0, "failed": 0, "blocked": 0}
    total = len(_audit_log)
    success = sum(1 for e in _audit_log if e["success"])
    blocked = sum(1 for e in _audit_log if not e["is_safe"])
    return {
        "total": total,
        "success": success,
        "failed": total - success - blocked,
        "blocked": blocked,
        "success_rate": round(success / total * 100, 1) if total else 0,
    }
