"""
learning/template_tracker.py — Template Performance Tracking
Tracks template success/failure rates, execution times, and user feedback.
Oracle-first with SQLite fallback.
"""
import logging
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.template")

_T = lambda: tbl("template_stats")


def track_template_use(
    template_name: str,
    success: bool,
    row_count: int,
    exec_ms: int,
) -> None:
    """Record a template execution outcome."""
    s = 1 if success else 0
    f = 0 if success else 1
    z = 1 if success and row_count == 0 else 0

    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                MERGE INTO {_T()} t
                USING (SELECT :1 AS tn FROM DUAL) s
                ON (t.TEMPLATE_NAME = s.tn)
                WHEN MATCHED THEN UPDATE SET
                    TOTAL_USES = t.TOTAL_USES + 1,
                    SUCCESS_COUNT = t.SUCCESS_COUNT + :2,
                    FAILURE_COUNT = t.FAILURE_COUNT + :3,
                    ZERO_RESULT_COUNT = t.ZERO_RESULT_COUNT + :4,
                    AVG_EXEC_MS = (t.AVG_EXEC_MS * t.TOTAL_USES + :5) / (t.TOTAL_USES + 1),
                    LAST_USED = SYSTIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (TEMPLATE_NAME, TOTAL_USES, SUCCESS_COUNT, FAILURE_COUNT,
                     ZERO_RESULT_COUNT, AVG_EXEC_MS, LAST_USED)
                VALUES (:6, 1, :7, :8, :9, :10, SYSTIMESTAMP)
            """, (template_name, s, f, z, exec_ms,
                  template_name, s, f, z, exec_ms))
        else:
            conn.execute(f"""
                INSERT INTO {_T()} (template_name, total_uses, success_count,
                                    failure_count, zero_result_count,
                                    avg_exec_ms, last_used)
                VALUES (?, 1, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(template_name) DO UPDATE SET
                    total_uses = total_uses + 1,
                    success_count = success_count + ?,
                    failure_count = failure_count + ?,
                    zero_result_count = zero_result_count + ?,
                    avg_exec_ms = (avg_exec_ms * total_uses + ?) / (total_uses + 1),
                    last_used = datetime('now')
            """, (template_name, s, f, z, exec_ms, s, f, z, exec_ms))


def get_template_stats(template_name: str = "") -> list[dict]:
    """Get performance stats for one or all templates."""
    with get_conn() as conn:
        if template_name:
            if is_oracle():
                rows = conn.execute(
                    f"SELECT * FROM {_T()} WHERE TEMPLATE_NAME = :1",
                    (template_name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {_T()} WHERE template_name = ?",
                    (template_name,)
                ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM {_T()} ORDER BY TOTAL_USES DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_best_templates(limit: int = 10) -> list[dict]:
    """Top templates by success rate (min 5 uses)."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT TEMPLATE_NAME, TOTAL_USES, SUCCESS_COUNT,
                       ROUND(100.0 * SUCCESS_COUNT / TOTAL_USES, 1) AS success_rate,
                       ROUND(AVG_EXEC_MS, 0) AS avg_ms,
                       USER_APPROVALS, USER_REJECTIONS
                FROM {_T()}
                WHERE TOTAL_USES >= 5
                ORDER BY success_rate DESC, TOTAL_USES DESC
                FETCH FIRST :1 ROWS ONLY
            """, (limit,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT template_name, total_uses, success_count,
                       ROUND(100.0 * success_count / total_uses, 1) AS success_rate,
                       ROUND(avg_exec_ms, 0) AS avg_ms,
                       user_approvals, user_rejections
                FROM {_T()}
                WHERE total_uses >= 5
                ORDER BY success_rate DESC, total_uses DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_worst_templates(limit: int = 10) -> list[dict]:
    """Templates with highest failure/rejection rate."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT TEMPLATE_NAME, TOTAL_USES,
                       FAILURE_COUNT, ZERO_RESULT_COUNT,
                       USER_REJECTIONS,
                       ROUND(100.0 * (FAILURE_COUNT + ZERO_RESULT_COUNT) / TOTAL_USES, 1)
                           AS problem_rate
                FROM {_T()}
                WHERE TOTAL_USES >= 3
                ORDER BY problem_rate DESC
                FETCH FIRST :1 ROWS ONLY
            """, (limit,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT template_name, total_uses,
                       failure_count, zero_result_count,
                       user_rejections,
                       ROUND(100.0 * (failure_count + zero_result_count) / total_uses, 1)
                           AS problem_rate
                FROM {_T()}
                WHERE total_uses >= 3
                ORDER BY problem_rate DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_template_score(template_name: str) -> float:
    """
    Calculate a trust score (0-1) for a template.
    Used by the pipeline to decide: use template or fallback to LLM?
    """
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT TOTAL_USES, SUCCESS_COUNT, FAILURE_COUNT,
                       ZERO_RESULT_COUNT, USER_APPROVALS, USER_REJECTIONS
                FROM {_T()} WHERE TEMPLATE_NAME = :1
            """, (template_name,)).fetchone()
        else:
            row = conn.execute(f"""
                SELECT total_uses, success_count, failure_count,
                       zero_result_count, user_approvals, user_rejections
                FROM {_T()} WHERE template_name = ?
            """, (template_name,)).fetchone()

    if not row:
        return 0.5  # no data

    total = row["total_uses"] or row.get("TOTAL_USES", 0)
    if total < 3:
        return 0.5

    success = row.get("success_count") or row.get("SUCCESS_COUNT", 0)
    approvals = row.get("user_approvals") or row.get("USER_APPROVALS", 0)
    rejections = row.get("user_rejections") or row.get("USER_REJECTIONS", 0)
    zero_count = row.get("zero_result_count") or row.get("ZERO_RESULT_COUNT", 0)

    base = success / total

    feedback_total = approvals + rejections
    if feedback_total > 0:
        feedback_bonus = 0.1 * (approvals - rejections) / feedback_total
        base += feedback_bonus

    zero_rate = zero_count / total
    base -= 0.15 * zero_rate

    return max(0.0, min(1.0, base))
