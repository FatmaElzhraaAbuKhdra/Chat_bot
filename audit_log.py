"""
audit_log.py — Enterprise Audit Log
Structured logging of all AI interactions for compliance, debugging,
and continuous improvement. Stores prompts, SQL, responses, and metadata.

Storage: learning/store.py backend (Oracle/SQLite)
Retention: configurable (default 90 days)
"""
import json
import time
import logging
from typing import Optional
from collections import deque

log = logging.getLogger("audit")

# In-memory buffer (flushed to DB periodically or on threshold)
_buffer: deque = deque(maxlen=1000)
_initialized = False


def log_interaction(
    user_id: str,
    question: str,
    intent_category: str = "",
    intent_sub: str = "",
    intent_confidence: float = 0.0,
    method: str = "",
    template_used: str = "",
    sql_generated: str = "",
    row_count: int = 0,
    answer_preview: str = "",
    execution_time_ms: int = 0,
    llm_provider: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_hit: bool = False,
    error: str = "",
    trace_id: str = "",
):
    """Log a complete interaction for audit trail."""
    entry = {
        "timestamp": time.time(),
        "trace_id": trace_id,
        "user_id": user_id,
        "question": question[:500],
        "intent_category": intent_category,
        "intent_sub": intent_sub,
        "intent_confidence": intent_confidence,
        "method": method,
        "template_used": template_used,
        "sql_generated": sql_generated[:1000] if sql_generated else "",
        "row_count": row_count,
        "answer_preview": answer_preview[:200],
        "execution_time_ms": execution_time_ms,
        "llm_provider": llm_provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_hit": cache_hit,
        "error": error[:500] if error else "",
    }
    _buffer.append(entry)

    # Flush to DB every 50 entries
    if len(_buffer) >= 50:
        _flush_to_db()


def get_recent(limit: int = 50) -> list[dict]:
    """Get recent audit entries (from memory buffer)."""
    return list(_buffer)[-limit:]


def get_stats() -> dict:
    """Audit statistics."""
    entries = list(_buffer)
    if not entries:
        return {"total": 0}

    methods = {}
    errors = 0
    cache_hits = 0
    for e in entries:
        m = e.get("method", "unknown")
        methods[m] = methods.get(m, 0) + 1
        if e.get("error"):
            errors += 1
        if e.get("cache_hit"):
            cache_hits += 1

    return {
        "total": len(entries),
        "methods": methods,
        "error_count": errors,
        "cache_hit_count": cache_hits,
        "buffer_size": len(_buffer),
    }


def _flush_to_db():
    """Persist buffer to database (best-effort)."""
    global _initialized
    try:
        from learning.store import get_conn, is_oracle
        # Ensure table exists
        if not _initialized:
            _ensure_table()
            _initialized = True

        entries = list(_buffer)
        if not entries:
            return

        with get_conn() as conn:
            if is_oracle():
                for e in entries[-50:]:  # flush last 50
                    conn.execute("""
                        INSERT INTO AI_AUDIT_LOG
                            (TRACE_ID, USER_ID, QUESTION, INTENT_CATEGORY,
                             INTENT_SUB, METHOD, TEMPLATE_USED, SQL_GENERATED,
                             ROW_COUNT, ANSWER_PREVIEW, EXECUTION_TIME_MS,
                             CACHE_HIT, ERROR_MSG, CREATED_AT)
                        VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,SYSTIMESTAMP)
                    """, (
                        e["trace_id"], e["user_id"], e["question"],
                        e["intent_category"], e["intent_sub"], e["method"],
                        e["template_used"], e["sql_generated"], e["row_count"],
                        e["answer_preview"], e["execution_time_ms"],
                        1 if e["cache_hit"] else 0, e["error"],
                    ))
            else:
                for e in entries[-50:]:
                    conn.execute("""
                        INSERT INTO audit_log
                            (trace_id, user_id, question, intent_category,
                             intent_sub, method, template_used, sql_generated,
                             row_count, answer_preview, execution_time_ms,
                             cache_hit, error_msg)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        e["trace_id"], e["user_id"], e["question"],
                        e["intent_category"], e["intent_sub"], e["method"],
                        e["template_used"], e["sql_generated"], e["row_count"],
                        e["answer_preview"], e["execution_time_ms"],
                        1 if e["cache_hit"] else 0, e["error"],
                    ))
    except Exception as ex:
        log.debug(f"[AUDIT] flush failed: {ex}")


def _ensure_table():
    """Create audit table if needed."""
    try:
        from learning.store import get_conn, is_oracle
        with get_conn() as conn:
            if is_oracle():
                conn.execute("""
                    BEGIN
                        EXECUTE IMMEDIATE '
                            CREATE TABLE AI_AUDIT_LOG (
                                ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                                TRACE_ID VARCHAR2(24),
                                USER_ID VARCHAR2(100),
                                QUESTION NVARCHAR2(500),
                                INTENT_CATEGORY VARCHAR2(50),
                                INTENT_SUB VARCHAR2(100),
                                METHOD VARCHAR2(50),
                                TEMPLATE_USED VARCHAR2(100),
                                SQL_GENERATED CLOB,
                                ROW_COUNT NUMBER,
                                ANSWER_PREVIEW NVARCHAR2(200),
                                EXECUTION_TIME_MS NUMBER,
                                CACHE_HIT NUMBER(1) DEFAULT 0,
                                ERROR_MSG VARCHAR2(500),
                                CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
                            )';
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                """)
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trace_id TEXT,
                        user_id TEXT,
                        question TEXT,
                        intent_category TEXT,
                        intent_sub TEXT,
                        method TEXT,
                        template_used TEXT,
                        sql_generated TEXT,
                        row_count INTEGER,
                        answer_preview TEXT,
                        execution_time_ms INTEGER,
                        cache_hit INTEGER DEFAULT 0,
                        error_msg TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_user
                    ON audit_log(user_id, created_at)
                """)
    except Exception:
        pass
