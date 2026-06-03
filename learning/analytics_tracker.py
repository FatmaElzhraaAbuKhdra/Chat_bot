"""
learning/analytics_tracker.py — Dashboard, KPI & Chart Preference Learning
Tracks dashboards, chart preferences, workflows, and predicts next intent.
Oracle-first with SQLite fallback.
"""
import json
import hashlib
import logging
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.analytics")

_T_AP = lambda: tbl("analytics_prefs")
_T_WP = lambda: tbl("workflow_patterns")


# ═══════════════════════════════════════════════════════════════════
# Cold-start Seed — common ERP intent sequences (frequency=5 so
# predict_next_intent() sees them immediately without waiting for 2 real uses)
# ═══════════════════════════════════════════════════════════════════

_SEED_WORKFLOW_PATTERNS = [
    ["sales_analysis", "customer_performance", "payment_collection"],
    ["sales_analysis", "invoice_detail", "customer_performance"],
    ["sales_analysis", "customer_performance"],
    ["customer_performance", "payment_collection", "accounting_summary"],
    ["customer_performance", "sales_analysis", "payment_collection"],
    ["payment_collection", "customer_performance", "accounting_summary"],
    ["purchasing_analysis", "inventory_movement", "item_analysis"],
    ["purchasing_analysis", "inventory_movement"],
    ["inventory_movement", "item_analysis", "purchasing_analysis"],
    ["inventory_movement", "item_analysis"],
    ["item_analysis", "inventory_movement", "sales_analysis"],
    ["accounting_summary", "payment_collection", "customer_performance"],
    ["accounting_summary", "trial_balance"],
    ["hr_payroll", "employee_detail", "attendance_analysis"],
    ["hr_payroll", "employee_detail"],
    ["employee_detail", "hr_payroll", "attendance_analysis"],
]

# Static fallback: given the last intent, what's likely next?
# Used when AI_WORKFLOW_PATTERNS is too sparse after seed but before real usage.
_ERP_FALLBACK_FLOWS: dict[str, list[str]] = {
    "sales_analysis":        ["customer_performance", "payment_collection", "invoice_detail"],
    "customer_performance":  ["payment_collection", "sales_analysis", "invoice_detail"],
    "payment_collection":    ["customer_performance", "accounting_summary", "sales_analysis"],
    "invoice_detail":        ["customer_performance", "sales_analysis"],
    "purchasing_analysis":   ["inventory_movement", "item_analysis", "vendor_analysis"],
    "inventory_movement":    ["item_analysis", "purchasing_analysis", "sales_analysis"],
    "item_analysis":         ["inventory_movement", "sales_analysis", "purchasing_analysis"],
    "vendor_analysis":       ["purchasing_analysis", "inventory_movement"],
    "accounting_summary":    ["payment_collection", "trial_balance", "customer_performance"],
    "trial_balance":         ["accounting_summary", "payment_collection"],
    "hr_payroll":            ["employee_detail", "attendance_analysis"],
    "employee_detail":       ["hr_payroll", "attendance_analysis"],
    "attendance_analysis":   ["employee_detail", "hr_payroll"],
}


def track_chart_preference(
    user_id: str,
    query_type: str,
    chart_type: str = "",
    limit_used: int = 0,
) -> None:
    """Track a user's chart/analytics preference."""
    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                MERGE INTO {_T_AP()} t
                USING (SELECT :1 AS uid, :2 AS qt FROM DUAL) s
                ON (t.USER_ID = s.uid AND t.QUERY_TYPE = s.qt)
                WHEN MATCHED THEN UPDATE SET
                    PREFERRED_CHART = CASE
                        WHEN :3 IS NOT NULL AND :4 != '' THEN :5
                        ELSE t.PREFERRED_CHART END,
                    PREFERRED_LIMIT = CASE
                        WHEN :6 > 0 THEN :7 ELSE t.PREFERRED_LIMIT END,
                    USAGE_COUNT = t.USAGE_COUNT + 1,
                    LAST_USED = SYSTIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (USER_ID, QUERY_TYPE, PREFERRED_CHART, PREFERRED_LIMIT,
                     USAGE_COUNT, LAST_USED)
                VALUES (:8, :9, :10, :11, 1, SYSTIMESTAMP)
            """, (user_id, query_type,
                  chart_type, chart_type, chart_type,
                  limit_used, limit_used,
                  user_id, query_type, chart_type, limit_used))
        else:
            conn.execute(f"""
                INSERT INTO {_T_AP()}
                    (user_id, query_type, preferred_chart, preferred_limit,
                     usage_count, last_used)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
                ON CONFLICT(user_id, query_type) DO UPDATE SET
                    preferred_chart = CASE
                        WHEN ? != '' THEN ? ELSE preferred_chart END,
                    preferred_limit = CASE
                        WHEN ? > 0 THEN ? ELSE preferred_limit END,
                    usage_count = usage_count + 1,
                    last_used = datetime('now')
            """, (user_id, query_type, chart_type, limit_used,
                  chart_type, chart_type, limit_used, limit_used))


def get_user_preferences(user_id: str) -> list[dict]:
    """Get a user's analytics preferences."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT QUERY_TYPE, PREFERRED_CHART, PREFERRED_LIMIT, USAGE_COUNT
                FROM {_T_AP()} WHERE USER_ID = :1
                ORDER BY USAGE_COUNT DESC
            """, (user_id,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT query_type, preferred_chart, preferred_limit, usage_count
                FROM {_T_AP()} WHERE user_id = ?
                ORDER BY usage_count DESC
            """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_preferred_chart(user_id: str, query_type: str) -> str | None:
    """Get preferred chart type for a specific query."""
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT PREFERRED_CHART FROM {_T_AP()}
                WHERE USER_ID = :1 AND QUERY_TYPE = :2
                  AND PREFERRED_CHART IS NOT NULL
            """, (user_id, query_type)).fetchone()
            return row["preferred_chart"] if row else None
        else:
            row = conn.execute(f"""
                SELECT preferred_chart FROM {_T_AP()}
                WHERE user_id = ? AND query_type = ?
                  AND preferred_chart IS NOT NULL
            """, (user_id, query_type)).fetchone()
            return row["preferred_chart"] if row else None


def get_popular_queries(limit: int = 10) -> list[dict]:
    """Most popular query types across all users."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT QUERY_TYPE,
                       SUM(USAGE_COUNT) AS total_uses,
                       COUNT(DISTINCT USER_ID) AS unique_users,
                       LISTAGG(DISTINCT PREFERRED_CHART, ',')
                           WITHIN GROUP (ORDER BY PREFERRED_CHART) AS chart_types
                FROM {_T_AP()}
                GROUP BY QUERY_TYPE
                ORDER BY total_uses DESC
                FETCH FIRST :1 ROWS ONLY
            """, (limit,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT query_type,
                       SUM(usage_count) AS total_uses,
                       COUNT(DISTINCT user_id) AS unique_users,
                       GROUP_CONCAT(DISTINCT preferred_chart) AS chart_types
                FROM {_T_AP()}
                GROUP BY query_type
                ORDER BY total_uses DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════
# Conversation Workflow Patterns
# ═══════════════════════════════════════════════════════════════════

def seed_workflow_patterns() -> int:
    """
    Seed AI_WORKFLOW_PATTERNS with common ERP sequences.
    Uses MERGE/INSERT IGNORE so re-running is safe.
    Seeds get frequency=5 so predict_next_intent() sees them on first call.
    """
    count = 0
    for seq in _SEED_WORKFLOW_PATTERNS:
        seq_json = json.dumps(seq)
        seq_hash = hashlib.md5(seq_json.encode()).hexdigest()
        try:
            with get_conn() as conn:
                if is_oracle():
                    conn.execute(f"""
                        MERGE INTO {_T_WP()} t
                        USING (SELECT :1 AS sh FROM DUAL) s
                        ON (t.SEQUENCE_HASH = s.sh)
                        WHEN NOT MATCHED THEN INSERT
                            (SEQUENCE_JSON, SEQUENCE_HASH, FREQUENCY, LAST_SEEN)
                        VALUES (:2, :3, 5, SYSTIMESTAMP)
                    """, (seq_hash, seq_json, seq_hash))
                else:
                    conn.execute(f"""
                        INSERT INTO {_T_WP()}
                            (sequence_json, sequence_hash, frequency, last_seen)
                        VALUES (?, ?, 5, datetime('now'))
                        ON CONFLICT(sequence_hash) DO NOTHING
                    """, (seq_json, seq_hash))
            count += 1
        except Exception as e:
            log.debug(f"[ANALYTICS] seed_workflow skip: {e}")
    log.info(f"[ANALYTICS] Seeded {count} workflow patterns")
    return count


def track_workflow(sequence: list[str]) -> None:
    """Track a conversation workflow pattern."""
    if len(sequence) < 2:
        return

    seq = sequence[-5:]
    seq_json = json.dumps(seq)
    seq_hash = hashlib.md5(seq_json.encode()).hexdigest()

    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                MERGE INTO {_T_WP()} t
                USING (SELECT :1 AS sh FROM DUAL) s
                ON (t.SEQUENCE_HASH = s.sh)
                WHEN MATCHED THEN UPDATE SET
                    FREQUENCY = t.FREQUENCY + 1,
                    LAST_SEEN = SYSTIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (SEQUENCE_JSON, SEQUENCE_HASH, FREQUENCY, LAST_SEEN)
                VALUES (:2, :3, 1, SYSTIMESTAMP)
            """, (seq_hash, seq_json, seq_hash))
        else:
            conn.execute(f"""
                INSERT INTO {_T_WP()}
                    (sequence_json, sequence_hash, frequency, last_seen)
                VALUES (?, ?, 1, datetime('now'))
                ON CONFLICT(sequence_hash) DO UPDATE SET
                    frequency = frequency + 1,
                    last_seen = datetime('now')
            """, (seq_json, seq_hash))


def predict_next_intent(recent_intents: list[str], top_k: int = 3) -> list[dict]:
    """Predict next intent from recent conversation sequence."""
    if not recent_intents:
        return []

    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT SEQUENCE_JSON, FREQUENCY
                FROM {_T_WP()}
                WHERE FREQUENCY >= 2
                ORDER BY FREQUENCY DESC
                FETCH FIRST 100 ROWS ONLY
            """).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT sequence_json, frequency
                FROM {_T_WP()}
                WHERE frequency >= 2
                ORDER BY frequency DESC LIMIT 100
            """).fetchall()

    predictions: dict[str, int] = {}
    recent = recent_intents[-3:]

    for row in rows:
        d = dict(row)
        seq_raw = d.get("sequence_json") or d.get("SEQUENCE_JSON", "[]")
        freq = d.get("frequency") or d.get("FREQUENCY", 0)
        try:
            seq = json.loads(seq_raw)
        except (json.JSONDecodeError, TypeError):
            continue

        for i in range(len(seq) - 1):
            window = seq[i:i + len(recent)]
            if window == recent and i + len(recent) < len(seq):
                next_intent = seq[i + len(recent)]
                predictions[next_intent] = predictions.get(next_intent, 0) + freq

    if predictions:
        results = [{"intent": k, "confidence": v} for k, v in predictions.items()]
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:top_k]

    # Cold-start fallback: static ERP transition map when DB is too sparse
    current = recent_intents[-1]
    fallback = _ERP_FALLBACK_FLOWS.get(current, [])
    return [{"intent": f, "confidence": 1} for f in fallback[:top_k]]


def get_common_workflows(limit: int = 10) -> list[dict]:
    """Get the most common conversation workflows."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT SEQUENCE_JSON, FREQUENCY, LAST_SEEN
                FROM {_T_WP()}
                ORDER BY FREQUENCY DESC
                FETCH FIRST :1 ROWS ONLY
            """, (limit,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT sequence_json, frequency, last_seen
                FROM {_T_WP()}
                ORDER BY frequency DESC LIMIT ?
            """, (limit,)).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            seq_key = "sequence_json" if "sequence_json" in d else "SEQUENCE_JSON"
            try:
                d["sequence"] = json.loads(d.pop(seq_key, "[]"))
            except (json.JSONDecodeError, TypeError):
                d["sequence"] = []
            results.append(d)
        return results
