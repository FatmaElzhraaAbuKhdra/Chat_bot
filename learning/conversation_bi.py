"""
learning/conversation_bi.py — Conversational BI Context Engine
Maintains conversation context for multi-step analytics.
Enables follow-up queries like "break it down by month" or "show only top 5".
"""
import json
import re
import time
import logging
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.bi")

_T = lambda: tbl("bi_context")


# ═══════════════════════════════════════════════════════════════════
# Context Structure
# ═══════════════════════════════════════════════════════════════════

def _empty_context() -> dict:
    """Create an empty BI context."""
    return {
        "last_query": None,
        "last_sql": None,
        "last_intent": None,
        "last_domain": None,
        "last_tables": [],
        "last_filters": {},
        "txn_context": {},          # FIX: comment-derived txn flags (e.g. {"INVTYPE": 0})
        "last_entity": None,        # FIX: primary entity/table of the last query
        "last_columns": [],
        "last_row_count": 0,
        "last_chart_type": None,
        "drill_stack": [],          # stack of previous contexts for drill-up
        "applied_modifiers": [],    # "top 5", "by month", "ascending"
        "conversation_turns": 0,
    }


# ═══════════════════════════════════════════════════════════════════
# Context CRUD
# ═══════════════════════════════════════════════════════════════════

def get_context(session_id: str) -> dict:
    """Get or create BI context for a session."""
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT CONTEXT_JSON FROM {_T()}
                WHERE SESSION_ID = :1
                ORDER BY UPDATED_AT DESC
                FETCH FIRST 1 ROW ONLY
            """, (session_id,)).fetchone()
        else:
            row = conn.execute(f"""
                SELECT context_json FROM {_T()}
                WHERE session_id = ?
                ORDER BY updated_at DESC LIMIT 1
            """, (session_id,)).fetchone()

    if row:
        # FIX: SQLite returns a bare sqlite3.Row (no .get); normalize to dict first
        d = dict(row)
        raw = d.get("context_json") or d.get("CONTEXT_JSON", "{}")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

    return _empty_context()


def save_context(session_id: str, context: dict,
                 user_id: str = "") -> None:
    """Save BI context for a session."""
    ctx_json = json.dumps(context, ensure_ascii=False, default=str)

    with get_conn() as conn:
        if is_oracle():
            # Check if exists
            exists = conn.execute(f"""
                SELECT ID FROM {_T()} WHERE SESSION_ID = :1
                FETCH FIRST 1 ROW ONLY
            """, (session_id,)).fetchone()

            if exists:
                exists = dict(exists)  # ROW SAFETY: normalize before .get()
                eid = exists.get("id") or exists.get("ID")
                conn.execute(f"""
                    UPDATE {_T()}
                    SET CONTEXT_JSON = :1, UPDATED_AT = SYSTIMESTAMP
                    WHERE ID = :2
                """, (ctx_json, eid))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (SESSION_ID, USER_ID, CONTEXT_JSON,
                         EXPIRES_AT)
                    VALUES (:1, :2, :3,
                            SYSTIMESTAMP + INTERVAL '24' HOUR)
                """, (session_id, user_id, ctx_json))
        else:
            exists = conn.execute(f"""
                SELECT id FROM {_T()} WHERE session_id = ? LIMIT 1
            """, (session_id,)).fetchone()

            if exists:
                conn.execute(f"""
                    UPDATE {_T()}
                    SET context_json = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (ctx_json, exists["id"]))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (session_id, user_id, context_json,
                         expires_at)
                    VALUES (?, ?, ?,
                            datetime('now', '+24 hours'))
                """, (session_id, user_id, ctx_json))


def clear_context(session_id: str) -> None:
    """Clear BI context for a session."""
    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                DELETE FROM {_T()} WHERE SESSION_ID = :1
            """, (session_id,))
        else:
            conn.execute(f"""
                DELETE FROM {_T()} WHERE session_id = ?
            """, (session_id,))


# ═══════════════════════════════════════════════════════════════════
# Context Updates (after each query)
# ═══════════════════════════════════════════════════════════════════

def update_context_after_query(
    session_id: str,
    question: str,
    sql: str,
    sub_intent: str,
    domain: str,
    tables: list[str],
    columns: list[str],
    filters: dict,
    row_count: int,
    chart_type: str = "",
    user_id: str = "",
    txn_context: dict = None,
    last_entity: str = "",
) -> dict:
    """Update BI context after a successful query."""
    ctx = get_context(session_id)

    # Push current to drill stack (for drill-up)
    if ctx.get("last_query"):
        drill_entry = {
            "query": ctx["last_query"],
            "sql": ctx["last_sql"],
            "intent": ctx["last_intent"],
        }
        stack = ctx.get("drill_stack", [])
        stack.append(drill_entry)
        ctx["drill_stack"] = stack[-5:]  # keep last 5

    # Update with new query info
    ctx["last_query"] = question
    ctx["last_sql"] = sql
    ctx["last_intent"] = sub_intent
    ctx["last_domain"] = domain
    ctx["last_tables"] = tables
    ctx["last_filters"] = filters
    ctx["last_columns"] = columns
    ctx["last_row_count"] = row_count
    ctx["last_chart_type"] = chart_type
    # FIX 5: txn_context / last_entity are sticky — NEVER auto-reset. They change
    # only when the new query carries its own (explicit switch), per the context rule.
    if txn_context:
        ctx["txn_context"] = txn_context
    if last_entity:
        ctx["last_entity"] = last_entity
    ctx["conversation_turns"] = ctx.get("conversation_turns", 0) + 1
    ctx["applied_modifiers"] = []  # reset modifiers for new query

    save_context(session_id, ctx, user_id)
    return ctx


# ═══════════════════════════════════════════════════════════════════
# Follow-up Query Detection
# ═══════════════════════════════════════════════════════════════════

_MODIFIER_PATTERNS = {
    # Arabic + English patterns for query modifiers
    "top_n": [
        r"اعلي\s+(\d+)", r"اعلى\s+(\d+)", r"أعلى\s+(\d+)",
        r"top\s+(\d+)", r"اول\s+(\d+)", r"أول\s+(\d+)",
    ],
    "bottom_n": [
        r"اقل\s+(\d+)", r"أقل\s+(\d+)", r"اخر\s+(\d+)",
        r"bottom\s+(\d+)", r"last\s+(\d+)",
    ],
    "group_by_month": [
        r"بالشهر", r"شهري", r"per month", r"by month", r"monthly",
    ],
    "group_by_year": [
        r"بالسنة", r"سنوي", r"per year", r"by year", r"yearly",
    ],
    "ascending": [
        r"تصاعدي", r"من الاقل", r"ascending", r"asc",
    ],
    "descending": [
        r"تنازلي", r"من الاعلى", r"descending", r"desc",
    ],
    "drill_up": [
        r"ارجع", r"الاجمالي", r"go back", r"summary", r"total",
    ],
}


def detect_modifier(question: str) -> dict | None:
    """Detect if a question is a modifier on the previous query."""
    import re
    question_lower = question.lower().strip()

    for mod_type, patterns in _MODIFIER_PATTERNS.items():
        for pat in patterns:
            match = re.search(pat, question_lower)
            if match:
                value = match.group(1) if match.lastindex else None
                return {
                    "type": mod_type,
                    "value": int(value) if value and value.isdigit() else None,
                    "pattern": pat,
                }

    return None


def is_followup(question: str, session_id: str) -> bool:
    """
    Determine if a question is a follow-up to the previous query.
    Returns True if the question references the previous context.
    """
    ctx = get_context(session_id)
    if not ctx.get("last_query"):
        return False  # no previous context

    # Short questions (< 5 words) with modifiers are likely follow-ups
    words = question.strip().split()
    if len(words) <= 5 and detect_modifier(question):
        return True

    # Pronouns and references
    followup_cues = [
        "هؤلاء", "هذه", "هذا", "دول", "اللي فاتت", "السابق",
        "نفس", "بتاعهم", "بتاعت", "the same", "these", "those",
        "previous", "last", "above",
    ]
    q_lower = question.lower()
    if any(cue in q_lower for cue in followup_cues):
        return True

    # FIX 3: a detail/instance reference with no new domain is a continuation —
    # e.g. "تفاصيل فاتورة 10", "اعرضها", "رقم 10" — so it inherits prior context.
    if re.search(r'(تفاصيل|اعرضها|اعرضه|رقم\s*\d|فاتور[ةه]\s*\d|^\s*\d+\s*$)',
                 question.strip()):
        return True

    return False


def build_followup_context(session_id: str) -> str:
    """Build a context string for the LLM when handling follow-ups."""
    ctx = get_context(session_id)
    if not ctx.get("last_query"):
        return ""

    parts = ["══ سياق المحادثة السابق ══"]
    parts.append(f"السؤال السابق: {ctx['last_query']}")
    if ctx.get("last_intent"):
        parts.append(f"Intent: {ctx['last_intent']}")
    if ctx.get("last_tables"):
        parts.append(f"الجداول: {', '.join(ctx['last_tables'])}")
    if ctx.get("last_sql"):
        # Truncate long SQL
        sql = ctx["last_sql"][:300]
        parts.append(f"SQL السابق: {sql}")
    if ctx.get("last_filters"):
        parts.append(f"الفلاتر: {json.dumps(ctx['last_filters'], ensure_ascii=False)}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════

def cleanup_expired() -> int:
    """Remove expired BI contexts."""
    with get_conn() as conn:
        if is_oracle():
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE EXPIRES_AT IS NOT NULL AND EXPIRES_AT < SYSTIMESTAMP
            """)
        else:
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
            """)
        deleted = cur.rowcount
        if deleted:
            log.info(f"[BI] Cleaned up {deleted} expired contexts")
        return deleted
