"""
learning/visualization.py — AI Visualization Intelligence
Learns optimal chart types based on data shape, domain, user feedback.
Provides smart chart recommendations for any query result.
"""
import json
import hashlib
import logging
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.viz")

_T = lambda: tbl("viz_rules")


# ═══════════════════════════════════════════════════════════════════
# Data Shape Analysis
# ═══════════════════════════════════════════════════════════════════

class DataShape:
    """Classify query result shapes for chart selection."""
    SINGLE_VALUE = "single_value"       # 1 row, 1 numeric col
    CATEGORY_VALUE = "category_value"   # N rows, 1 label + 1 value
    TIME_SERIES = "time_series"         # date/month col + value(s)
    MULTI_SERIES = "multi_series"       # date + multiple value cols
    RANKING = "ranking"                 # sorted by value, top-N
    TABULAR = "tabular"                 # many cols, best as table
    COMPARISON = "comparison"           # few rows, multiple metrics


def analyze_data_shape(rows: list[dict], sub_intent: str = "") -> str:
    """Determine the data shape from query results."""
    if not rows:
        return DataShape.TABULAR

    n_rows = len(rows)
    cols = list(rows[0].keys())
    n_cols = len(cols)

    # Filter out metadata columns
    cols = [c for c in cols if not c.startswith("__")]
    n_cols = len(cols)

    if n_rows == 1 and n_cols <= 2:
        return DataShape.SINGLE_VALUE

    # Check for time dimension
    time_keywords = {"شهر", "month", "date", "year", "سنة", "تاريخ",
                     "يوم", "day", "week", "اسبوع", "quarter", "ربع"}
    has_time = any(
        any(tk in col.lower() for tk in time_keywords)
        for col in cols
    )

    # Count numeric vs text columns
    sample = rows[0]
    numeric_cols = sum(1 for c in cols
                       if isinstance(sample.get(c), (int, float)))
    text_cols = n_cols - numeric_cols

    if has_time and numeric_cols >= 1:
        if numeric_cols >= 2:
            return DataShape.MULTI_SERIES
        return DataShape.TIME_SERIES

    if text_cols == 1 and numeric_cols == 1:
        if n_rows <= 15:
            return DataShape.CATEGORY_VALUE
        return DataShape.RANKING

    if n_rows <= 5 and numeric_cols >= 2:
        return DataShape.COMPARISON

    if text_cols >= 1 and numeric_cols >= 1 and n_rows <= 20:
        # Check if sorted by the numeric column (ranking)
        first_num_col = next(
            (c for c in cols if isinstance(sample.get(c), (int, float))),
            None
        )
        if first_num_col and n_rows >= 3:
            vals = [r.get(first_num_col, 0) for r in rows[:5]]
            if vals == sorted(vals, reverse=True):
                return DataShape.RANKING

        return DataShape.CATEGORY_VALUE

    return DataShape.TABULAR


# ═══════════════════════════════════════════════════════════════════
# Chart Recommendation Engine
# ═══════════════════════════════════════════════════════════════════

# Default recommendations per data shape
_DEFAULT_CHARTS = {
    DataShape.SINGLE_VALUE: "metric",      # big number display
    DataShape.CATEGORY_VALUE: "bar",
    DataShape.TIME_SERIES: "line",
    DataShape.MULTI_SERIES: "line",
    DataShape.RANKING: "horizontal_bar",
    DataShape.TABULAR: "table",
    DataShape.COMPARISON: "bar",
}


def recommend_chart(
    rows: list[dict],
    domain: str = "",
    sub_intent: str = "",
    user_id: str = "",
) -> dict:
    """
    Recommend the best chart type for given data.
    Considers data shape, learned rules, and user preferences.
    """
    data_shape = analyze_data_shape(rows, sub_intent)

    # 1. Check learned rules
    learned = _get_learned_rule(domain, sub_intent, data_shape)
    if learned and learned.get("score", 0) >= 3.0:
        return {
            "chart_type": learned["best_chart"],
            "data_shape": data_shape,
            "source": "learned",
            "confidence": min(1.0, learned["score"] / 10),
        }

    # 2. Check user preference
    if user_id:
        from .analytics_tracker import get_preferred_chart
        pref = get_preferred_chart(user_id, sub_intent or data_shape)
        if pref:
            return {
                "chart_type": pref,
                "data_shape": data_shape,
                "source": "user_preference",
                "confidence": 0.85,
            }

    # 3. Default by data shape
    chart_type = _DEFAULT_CHARTS.get(data_shape, "table")

    # Domain-specific overrides
    if domain == "accounting" and data_shape == DataShape.CATEGORY_VALUE:
        if sub_intent and "revenue" in sub_intent:
            chart_type = "bar"  # grouped bar for revenue/expense
    elif domain == "invoicing" and data_shape == DataShape.RANKING:
        chart_type = "horizontal_bar"

    return {
        "chart_type": chart_type,
        "data_shape": data_shape,
        "source": "default",
        "confidence": 0.6,
    }


def _get_learned_rule(domain: str, sub_intent: str,
                      data_shape: str) -> dict | None:
    """Get learned visualization rule."""
    rule_key = _make_rule_key(domain, sub_intent, data_shape)
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT BEST_CHART, SCORE, USAGE_COUNT, FEEDBACK_SCORE
                FROM {_T()} WHERE RULE_KEY = :1
            """, (rule_key,)).fetchone()
        else:
            row = conn.execute(f"""
                SELECT best_chart, score, usage_count, feedback_score
                FROM {_T()} WHERE rule_key = ?
            """, (rule_key,)).fetchone()
        return dict(row) if row else None


def _make_rule_key(domain: str, sub_intent: str, data_shape: str) -> str:
    """Build a unique rule key."""
    return f"{domain}:{sub_intent}:{data_shape}"


# ═══════════════════════════════════════════════════════════════════
# Learning from User Behavior
# ═══════════════════════════════════════════════════════════════════

def record_chart_selection(
    domain: str,
    sub_intent: str,
    data_shape: str,
    chart_type: str,
    feedback_score: float = 0.0,
) -> None:
    """Record that a chart type was used/selected for a data shape."""
    rule_key = _make_rule_key(domain, sub_intent, data_shape)

    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                MERGE INTO {_T()} t
                USING (SELECT :1 AS rk FROM DUAL) s
                ON (t.RULE_KEY = s.rk)
                WHEN MATCHED THEN UPDATE SET
                    BEST_CHART = CASE
                        WHEN :2 > t.FEEDBACK_SCORE THEN :3
                        ELSE t.BEST_CHART END,
                    SCORE = t.SCORE + 1 + :4,
                    USAGE_COUNT = t.USAGE_COUNT + 1,
                    FEEDBACK_SCORE = GREATEST(t.FEEDBACK_SCORE, :5),
                    UPDATED_AT = SYSTIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (RULE_KEY, DOMAIN, SUB_INTENT, DATA_SHAPE, BEST_CHART,
                     SCORE, USAGE_COUNT, FEEDBACK_SCORE)
                VALUES (:6, :7, :8, :9, :10, 1 + :11, 1, :12)
            """, (rule_key, feedback_score, chart_type, feedback_score,
                  feedback_score,
                  rule_key, domain, sub_intent, data_shape, chart_type,
                  feedback_score, feedback_score))
        else:
            conn.execute(f"""
                INSERT INTO {_T()}
                    (rule_key, domain, sub_intent, data_shape, best_chart,
                     score, usage_count, feedback_score)
                VALUES (?, ?, ?, ?, ?, 1 + ?, 1, ?)
                ON CONFLICT(rule_key) DO UPDATE SET
                    best_chart = CASE
                        WHEN ? > feedback_score THEN ?
                        ELSE best_chart END,
                    score = score + 1 + ?,
                    usage_count = usage_count + 1,
                    feedback_score = MAX(feedback_score, ?),
                    updated_at = datetime('now')
            """, (rule_key, domain, sub_intent, data_shape, chart_type,
                  feedback_score, feedback_score,
                  feedback_score, chart_type,
                  feedback_score, feedback_score))


def get_viz_stats() -> dict:
    """Get visualization learning statistics."""
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT COUNT(*) AS total_rules,
                   COUNT(DISTINCT data_shape) AS data_shapes,
                   COUNT(DISTINCT best_chart) AS chart_types,
                   SUM(usage_count) AS total_selections
            FROM {_T()}
        """).fetchone()
        return dict(row) if row else {}
