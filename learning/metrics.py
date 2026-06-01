"""
learning/metrics.py — Enterprise Observability & Metrics
Tracks learning quality, system performance, and operational health.
Stores metrics in DB for time-series analysis and alerting.
"""
import time
import logging
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.metrics")

_T = lambda: tbl("metrics")


# ═══════════════════════════════════════════════════════════════════
# Metric Names
# ═══════════════════════════════════════════════════════════════════

class MetricName:
    # Query performance
    QUERY_LATENCY_MS = "query_latency_ms"
    QUERY_SUCCESS_RATE = "query_success_rate"
    QUERY_ZERO_RESULT_RATE = "query_zero_result_rate"

    # Intent classification
    INTENT_CONFIDENCE = "intent_confidence"
    INTENT_REGEX_HIT_RATE = "intent_regex_hit_rate"
    INTENT_LLM_FALLBACK_RATE = "intent_llm_fallback_rate"

    # Template performance
    TEMPLATE_HIT_RATE = "template_hit_rate"
    TEMPLATE_SUCCESS_RATE = "template_success_rate"

    # Learning effectiveness
    FEEDBACK_RATE = "feedback_rate"
    APPROVAL_RATE = "approval_rate"
    SYNONYM_HIT_RATE = "synonym_hit_rate"
    EMBEDDING_CACHE_HIT = "embedding_cache_hit"

    # System health
    DB_RESPONSE_TIME_MS = "db_response_time_ms"
    LLM_RESPONSE_TIME_MS = "llm_response_time_ms"
    ACTIVE_SESSIONS = "active_sessions"
    EVENTS_PENDING = "events_pending"


# ═══════════════════════════════════════════════════════════════════
# Record Metrics
# ═══════════════════════════════════════════════════════════════════

def record(metric_name: str, value: float,
           dimension: str = "") -> None:
    """Record a single metric point."""
    try:
        with get_conn() as conn:
            if is_oracle():
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (METRIC_NAME, METRIC_VALUE, DIMENSION)
                    VALUES (:1, :2, :3)
                """, (metric_name, value, dimension))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (metric_name, metric_value, dimension)
                    VALUES (?, ?, ?)
                """, (metric_name, value, dimension))
    except Exception as e:
        log.debug(f"[METRICS] Record failed: {e}")


def record_batch(metrics: list[tuple]) -> None:
    """
    Record multiple metrics at once.
    Each tuple: (metric_name, value, dimension)
    """
    try:
        with get_conn() as conn:
            for name, value, dim in metrics:
                if is_oracle():
                    conn.execute(f"""
                        INSERT INTO {_T()}
                            (METRIC_NAME, METRIC_VALUE, DIMENSION)
                        VALUES (:1, :2, :3)
                    """, (name, value, dim))
                else:
                    conn.execute(f"""
                        INSERT INTO {_T()}
                            (metric_name, metric_value, dimension)
                        VALUES (?, ?, ?)
                    """, (name, value, dim))
    except Exception as e:
        log.debug(f"[METRICS] Batch record failed: {e}")


# ═══════════════════════════════════════════════════════════════════
# Timer Context Manager
# ═══════════════════════════════════════════════════════════════════

class timer:
    """Context manager to time operations and record as metrics."""

    def __init__(self, metric_name: str, dimension: str = ""):
        self.metric_name = metric_name
        self.dimension = dimension
        self.start_time = None
        self.elapsed_ms = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        record(self.metric_name, self.elapsed_ms, self.dimension)
        return False  # don't suppress exceptions


# ═══════════════════════════════════════════════════════════════════
# Query Metrics
# ═══════════════════════════════════════════════════════════════════

def get_metric_summary(metric_name: str, hours: int = 24) -> dict:
    """Get aggregate stats for a metric over the last N hours."""
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT COUNT(*) AS count,
                       ROUND(AVG(METRIC_VALUE), 2) AS avg_value,
                       ROUND(MIN(METRIC_VALUE), 2) AS min_value,
                       ROUND(MAX(METRIC_VALUE), 2) AS max_value,
                       ROUND(MEDIAN(METRIC_VALUE), 2) AS p50,
                       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP
                           (ORDER BY METRIC_VALUE), 2) AS p95,
                       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP
                           (ORDER BY METRIC_VALUE), 2) AS p99
                FROM {_T()}
                WHERE METRIC_NAME = :1
                  AND RECORDED_AT >= SYSTIMESTAMP - NUMTODSINTERVAL(:2, 'HOUR')
            """, (metric_name, hours)).fetchone()
        else:
            row = conn.execute(f"""
                SELECT COUNT(*) AS count,
                       ROUND(AVG(metric_value), 2) AS avg_value,
                       ROUND(MIN(metric_value), 2) AS min_value,
                       ROUND(MAX(metric_value), 2) AS max_value
                FROM {_T()}
                WHERE metric_name = ?
                  AND recorded_at >= datetime('now', ? || ' hours')
            """, (metric_name, f"-{hours}")).fetchone()

        return dict(row) if row else {}


def get_metric_timeseries(metric_name: str, hours: int = 24,
                          bucket_minutes: int = 60) -> list[dict]:
    """Get time-bucketed metric data for charting."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT
                    TO_CHAR(TRUNC(RECORDED_AT, 'HH'), 'YYYY-MM-DD HH24:MI') AS bucket,
                    COUNT(*) AS count,
                    ROUND(AVG(METRIC_VALUE), 2) AS avg_value,
                    ROUND(MAX(METRIC_VALUE), 2) AS max_value
                FROM {_T()}
                WHERE METRIC_NAME = :1
                  AND RECORDED_AT >= SYSTIMESTAMP - NUMTODSINTERVAL(:2, 'HOUR')
                GROUP BY TRUNC(RECORDED_AT, 'HH')
                ORDER BY bucket
            """, (metric_name, hours)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    STRFTIME('%Y-%m-%d %H:00', recorded_at) AS bucket,
                    COUNT(*) AS count,
                    ROUND(AVG(metric_value), 2) AS avg_value,
                    ROUND(MAX(metric_value), 2) AS max_value
                FROM {_T()}
                WHERE metric_name = ?
                  AND recorded_at >= datetime('now', ? || ' hours')
                GROUP BY bucket
                ORDER BY bucket
            """, (metric_name, f"-{hours}")).fetchall()

        return [dict(r) for r in rows]


def get_all_metric_summaries(hours: int = 24) -> dict:
    """Get summaries for all tracked metrics."""
    with get_conn() as conn:
        if is_oracle():
            rows = conn.execute(f"""
                SELECT METRIC_NAME,
                       COUNT(*) AS count,
                       ROUND(AVG(METRIC_VALUE), 2) AS avg_value,
                       ROUND(MAX(METRIC_VALUE), 2) AS max_value
                FROM {_T()}
                WHERE RECORDED_AT >= SYSTIMESTAMP - NUMTODSINTERVAL(:1, 'HOUR')
                GROUP BY METRIC_NAME
                ORDER BY count DESC
            """, (hours,)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT metric_name,
                       COUNT(*) AS count,
                       ROUND(AVG(metric_value), 2) AS avg_value,
                       ROUND(MAX(metric_value), 2) AS max_value
                FROM {_T()}
                WHERE recorded_at >= datetime('now', ? || ' hours')
                GROUP BY metric_name
                ORDER BY count DESC
            """, (f"-{hours}",)).fetchall()

        result = {}
        for r in rows:
            d = dict(r)
            name = d.pop("metric_name", d.pop("METRIC_NAME", "unknown"))
            result[name] = d
        return result


# ═══════════════════════════════════════════════════════════════════
# Health Dashboard
# ═══════════════════════════════════════════════════════════════════

def get_health_report() -> dict:
    """
    Generate a health report for the learning engine.
    Checks key metrics and returns status indicators.
    """
    summaries = get_all_metric_summaries(hours=1)

    # Calculate health indicators
    indicators = {}

    # Query success rate
    qsr = summaries.get(MetricName.QUERY_SUCCESS_RATE, {})
    if qsr.get("count", 0) > 0:
        avg_sr = qsr.get("avg_value", 0)
        indicators["query_health"] = (
            "healthy" if avg_sr >= 0.8 else
            "degraded" if avg_sr >= 0.5 else
            "unhealthy"
        )

    # DB response time
    db_rt = summaries.get(MetricName.DB_RESPONSE_TIME_MS, {})
    if db_rt.get("count", 0) > 0:
        avg_rt = db_rt.get("avg_value", 0)
        indicators["db_health"] = (
            "healthy" if avg_rt < 500 else
            "degraded" if avg_rt < 2000 else
            "unhealthy"
        )

    # Approval rate
    ar = summaries.get(MetricName.APPROVAL_RATE, {})
    if ar.get("count", 0) > 0:
        avg_ar = ar.get("avg_value", 0)
        indicators["learning_health"] = (
            "healthy" if avg_ar >= 0.7 else
            "degraded" if avg_ar >= 0.4 else
            "needs_attention"
        )

    return {
        "status": "healthy" if all(
            v == "healthy" for v in indicators.values()
        ) else "degraded" if indicators else "no_data",
        "indicators": indicators,
        "metrics_1h": summaries,
    }


# ═══════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════

def cleanup_old_metrics(days: int = 7) -> int:
    """Delete metrics older than N days."""
    with get_conn() as conn:
        if is_oracle():
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE RECORDED_AT < SYSTIMESTAMP - NUMTODSINTERVAL(:1, 'DAY')
            """, (days,))
        else:
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE recorded_at < datetime('now', ? || ' days')
            """, (f"-{days}",))
        deleted = cur.rowcount
        if deleted:
            log.info(f"[METRICS] Cleaned up {deleted} old metric records")
        return deleted
