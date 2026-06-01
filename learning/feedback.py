"""
learning/feedback.py — Feedback Collection & Learning Pipeline
Captures user approval, rejection, correction, and rephrasing.
Works with both Oracle and SQLite backends.
"""
import json
import logging
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.feedback")

_T = lambda: tbl("feedback")
_T_TS = lambda: tbl("template_stats")
_T_LP = lambda: tbl("learned_patterns")


# ═══════════════════════════════════════════════════════════════════
# Record Feedback
# ═══════════════════════════════════════════════════════════════════

def record_feedback(
    user_id: str,
    question: str,
    feedback_type: str,
    category: str = "",
    domain: str = "",
    sub_intent: str = "",
    template_used: str = "",
    sql_generated: str = "",
    ai_response: str = "",
    corrected_response: str = "",
    corrected_sql: str = "",
    user_rephrased: str = "",
    rating: int = 0,
    notes: str = "",
) -> int:
    """Store user feedback and trigger learning side-effects."""
    with get_conn() as conn:
        if is_oracle():
            cur = conn.execute(f"""
                INSERT INTO {_T()}
                    (USER_ID, QUESTION, CATEGORY, DOMAIN, SUB_INTENT,
                     TEMPLATE_USED, SQL_GENERATED, AI_RESPONSE,
                     FEEDBACK_TYPE, CORRECTED_RESPONSE, CORRECTED_SQL,
                     USER_REPHRASED, RATING, NOTES)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14)
            """, (user_id, question, category, domain, sub_intent,
                  template_used, sql_generated, ai_response,
                  feedback_type, corrected_response, corrected_sql,
                  user_rephrased, rating, notes))
            # Get the generated ID
            row = conn.execute(
                f"SELECT MAX(ID) AS mid FROM {_T()}"
            ).fetchone()
            feedback_id = row["mid"] if row else 0
        else:
            cur = conn.execute(f"""
                INSERT INTO {_T()}
                    (user_id, question, category, domain, sub_intent,
                     template_used, sql_generated, ai_response,
                     feedback_type, corrected_response, corrected_sql,
                     user_rephrased, rating, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, question, category, domain, sub_intent,
                  template_used, sql_generated, ai_response,
                  feedback_type, corrected_response, corrected_sql,
                  user_rephrased, rating, notes))
            feedback_id = cur.lastrowid

    # Side-effects
    if template_used:
        _update_template_feedback(template_used, feedback_type)

    if feedback_type == "rephrase" and user_rephrased and sub_intent:
        _learn_from_rephrase(user_rephrased, sub_intent, domain)

    if feedback_type == "correct" and corrected_sql and question:
        _learn_from_correction(question, sub_intent, domain, corrected_sql)

    log.info(f"[LEARNING] Feedback recorded: type={feedback_type} "
             f"sub_intent={sub_intent} template={template_used}")
    return feedback_id


def _update_template_feedback(template_name: str, feedback_type: str):
    """Update template approval/rejection counts."""
    col = "user_approvals" if feedback_type == "approve" else "user_rejections"
    col_upper = col.upper()
    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                UPDATE {_T_TS()} SET {col_upper} = {col_upper} + 1
                WHERE TEMPLATE_NAME = :1
            """, (template_name,))
        else:
            conn.execute(f"""
                UPDATE {_T_TS()} SET {col} = {col} + 1
                WHERE template_name = ?
            """, (template_name,))


def _learn_from_rephrase(rephrased: str, sub_intent: str, domain: str):
    """Store user's phrasing as a learned pattern."""
    with get_conn() as conn:
        if is_oracle():
            # MERGE for upsert
            conn.execute(f"""
                MERGE INTO {_T_LP()} t
                USING (SELECT :1 AS q, :2 AS si, :3 AS d FROM DUAL) s
                ON (t.QUESTION = s.q AND t.SUB_INTENT = s.si)
                WHEN NOT MATCHED THEN
                    INSERT (QUESTION, SUB_INTENT, DOMAIN, SOURCE, CONFIDENCE)
                    VALUES (s.q, s.si, s.d, 'user_rephrase', 0.85)
            """, (rephrased, sub_intent, domain))
        else:
            conn.execute(f"""
                INSERT OR IGNORE INTO {_T_LP()}
                    (question, sub_intent, domain, source, confidence)
                VALUES (?, ?, ?, 'user_rephrase', 0.85)
            """, (rephrased, sub_intent, domain))


def _learn_from_correction(question: str, sub_intent: str,
                           domain: str, corrected_sql: str):
    """Learn from a SQL correction."""
    entities = json.dumps({"corrected_sql": corrected_sql})
    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                MERGE INTO {_T_LP()} t
                USING (SELECT :1 AS q, :2 AS si FROM DUAL) s
                ON (t.QUESTION = s.q AND t.SUB_INTENT = s.si)
                WHEN NOT MATCHED THEN
                    INSERT (QUESTION, SUB_INTENT, DOMAIN, SOURCE, CONFIDENCE, ENTITIES_JSON)
                    VALUES (s.q, s.si, :3, 'user_correction', 0.9, :4)
            """, (question, sub_intent, domain, entities))
        else:
            conn.execute(f"""
                INSERT OR IGNORE INTO {_T_LP()}
                    (question, sub_intent, domain, source, confidence, entities_json)
                VALUES (?, ?, ?, 'user_correction', 0.9, ?)
            """, (question, sub_intent, domain, entities))


# ═══════════════════════════════════════════════════════════════════
# Query Feedback Data
# ═══════════════════════════════════════════════════════════════════

def get_feedback_stats() -> dict:
    """Get overall feedback statistics."""
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN feedback_type='approve' THEN 1 ELSE 0 END) AS approvals,
                SUM(CASE WHEN feedback_type='reject' THEN 1 ELSE 0 END) AS rejections,
                SUM(CASE WHEN feedback_type='correct' THEN 1 ELSE 0 END) AS corrections,
                SUM(CASE WHEN feedback_type='rephrase' THEN 1 ELSE 0 END) AS rephrases,
                ROUND(AVG(CASE WHEN rating > 0 THEN rating END), 2) AS avg_rating
            FROM {_T()}
        """).fetchone()
        return dict(row) if row else {}


def get_feedback_by_intent(sub_intent: str, limit: int = 20) -> list[dict]:
    """Get recent feedback for a specific intent."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT * FROM {_T()}
                WHERE SUB_INTENT = :1
                ORDER BY CREATED_AT DESC
                FETCH FIRST :2 ROWS ONLY
            """, (sub_intent, limit)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT * FROM {_T()}
                WHERE sub_intent = ?
                ORDER BY created_at DESC LIMIT ?
            """, (sub_intent, limit)).fetchall()
        return [dict(r) for r in rows]


def get_approved_responses(sub_intent: str = "", limit: int = 50) -> list[dict]:
    """Get approved responses as gold-standard examples."""
    with get_conn() as conn:
        if is_oracle():
            if sub_intent:
                rows = conn.execute(f"""
                    SELECT QUESTION, AI_RESPONSE, SQL_GENERATED, TEMPLATE_USED
                    FROM {_T()}
                    WHERE FEEDBACK_TYPE = 'approve' AND SUB_INTENT = :1
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST :2 ROWS ONLY
                """, (sub_intent, limit)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT QUESTION, AI_RESPONSE, SQL_GENERATED, TEMPLATE_USED,
                           SUB_INTENT, DOMAIN
                    FROM {_T()}
                    WHERE FEEDBACK_TYPE = 'approve'
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST :1 ROWS ONLY
                """, (limit,)).fetchall()
        else:
            if sub_intent:
                rows = conn.execute(f"""
                    SELECT question, ai_response, sql_generated, template_used
                    FROM {_T()}
                    WHERE feedback_type = 'approve' AND sub_intent = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (sub_intent, limit)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT question, ai_response, sql_generated, template_used,
                           sub_intent, domain
                    FROM {_T()}
                    WHERE feedback_type = 'approve'
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_common_rejections(limit: int = 20) -> list[dict]:
    """Find the most commonly rejected intents."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT SUB_INTENT, TEMPLATE_USED,
                       COUNT(*) AS rejection_count,
                       LISTAGG(DISTINCT QUESTION, ' | ')
                           WITHIN GROUP (ORDER BY QUESTION) AS sample_questions
                FROM {_T()}
                WHERE FEEDBACK_TYPE IN ('reject', 'correct')
                GROUP BY SUB_INTENT, TEMPLATE_USED
                ORDER BY rejection_count DESC
                FETCH FIRST :1 ROWS ONLY
            """, (limit,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT sub_intent, template_used,
                       COUNT(*) AS rejection_count,
                       GROUP_CONCAT(DISTINCT question) AS sample_questions
                FROM {_T()}
                WHERE feedback_type IN ('reject', 'correct')
                GROUP BY sub_intent, template_used
                ORDER BY rejection_count DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
