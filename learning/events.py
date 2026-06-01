"""
learning/events.py — Event-Driven Learning Architecture
Decoupled event bus: components emit events, processors consume them.
Events are persisted in DB for reliability and replay.
"""
import json
import logging
import time
import threading
from typing import Callable, Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.events")

_T = lambda: tbl("events")

# ═══════════════════════════════════════════════════════════════════
# Event Types
# ═══════════════════════════════════════════════════════════════════

class EventType:
    """All known event types in the learning system."""
    QUERY_COMPLETED = "query_completed"
    FEEDBACK_RECEIVED = "feedback_received"
    TEMPLATE_USED = "template_used"
    INTENT_CLASSIFIED = "intent_classified"
    SQL_GENERATED = "sql_generated"
    SESSION_ENDED = "session_ended"
    SYNONYM_LEARNED = "synonym_learned"
    KNOWLEDGE_ADDED = "knowledge_added"
    VIZ_SELECTED = "viz_selected"
    CHART_PREFERENCE = "chart_preference"
    EMBEDDING_CACHED = "embedding_cached"
    SAFETY_VIOLATION = "safety_violation"
    ERROR_OCCURRED = "error_occurred"


# ═══════════════════════════════════════════════════════════════════
# Event Bus (in-process, sync)
# ═══════════════════════════════════════════════════════════════════

_handlers: dict[str, list[Callable]] = {}
_lock = threading.Lock()


def on(event_type: str, handler: Callable) -> None:
    """Register an event handler."""
    with _lock:
        if event_type not in _handlers:
            _handlers[event_type] = []
        _handlers[event_type].append(handler)
    log.debug(f"[EVENTS] Registered handler for {event_type}")


def off(event_type: str, handler: Callable) -> None:
    """Remove an event handler."""
    with _lock:
        if event_type in _handlers:
            _handlers[event_type] = [
                h for h in _handlers[event_type] if h != handler
            ]


def emit(event_type: str, data: dict, user_id: str = "",
         persist: bool = True) -> None:
    """
    Emit an event: persist to DB and dispatch to handlers.
    Non-blocking: handler failures don't propagate.
    """
    # Persist to database
    if persist:
        try:
            _persist_event(event_type, data, user_id)
        except Exception as e:
            log.warning(f"[EVENTS] Failed to persist {event_type}: {e}")

    # Dispatch to registered handlers
    handlers_copy = []
    with _lock:
        handlers_copy = list(_handlers.get(event_type, []))
        # Also dispatch to wildcard handlers
        handlers_copy.extend(_handlers.get("*", []))

    for handler in handlers_copy:
        try:
            handler(event_type, data, user_id)
        except Exception as e:
            log.warning(f"[EVENTS] Handler error for {event_type}: {e}")


def _persist_event(event_type: str, data: dict, user_id: str):
    """Store event in database for replay and audit."""
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    with get_conn() as conn:
        if is_oracle():
            conn.execute(f"""
                INSERT INTO {_T()} (EVENT_TYPE, EVENT_DATA, USER_ID)
                VALUES (:1, :2, :3)
            """, (event_type, data_json, user_id))
        else:
            conn.execute(f"""
                INSERT INTO {_T()} (event_type, event_data, user_id)
                VALUES (?, ?, ?)
            """, (event_type, data_json, user_id))


# ═══════════════════════════════════════════════════════════════════
# Event Processing (batch replay)
# ═══════════════════════════════════════════════════════════════════

def get_unprocessed(event_type: str = "", limit: int = 100) -> list[dict]:
    """Get unprocessed events for batch processing."""
    with get_conn() as conn:
        if is_oracle():
            if event_type:
                rows = conn.execute(f"""
                    SELECT ID, EVENT_TYPE, EVENT_DATA, USER_ID, CREATED_AT
                    FROM {_T()}
                    WHERE PROCESSED = 0 AND EVENT_TYPE = :1
                    ORDER BY CREATED_AT ASC
                    FETCH FIRST :2 ROWS ONLY
                """, (event_type, limit)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT ID, EVENT_TYPE, EVENT_DATA, USER_ID, CREATED_AT
                    FROM {_T()}
                    WHERE PROCESSED = 0
                    ORDER BY CREATED_AT ASC
                    FETCH FIRST :1 ROWS ONLY
                """, (limit,)).fetchall()
        else:
            if event_type:
                rows = conn.execute(f"""
                    SELECT id, event_type, event_data, user_id, created_at
                    FROM {_T()}
                    WHERE processed = 0 AND event_type = ?
                    ORDER BY created_at ASC LIMIT ?
                """, (event_type, limit)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT id, event_type, event_data, user_id, created_at
                    FROM {_T()}
                    WHERE processed = 0
                    ORDER BY created_at ASC LIMIT ?
                """, (limit,)).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            data_key = "event_data" if "event_data" in d else "EVENT_DATA"
            try:
                d["data"] = json.loads(d.pop(data_key, "{}"))
            except (json.JSONDecodeError, TypeError):
                d["data"] = {}
            results.append(d)
        return results


def mark_processed(event_ids: list[int]) -> None:
    """Mark events as processed."""
    if not event_ids:
        return
    with get_conn() as conn:
        if is_oracle():
            # Batch update
            for eid in event_ids:
                conn.execute(f"""
                    UPDATE {_T()} SET PROCESSED = 1 WHERE ID = :1
                """, (eid,))
        else:
            placeholders = ",".join("?" for _ in event_ids)
            conn.execute(f"""
                UPDATE {_T()} SET processed = 1
                WHERE id IN ({placeholders})
            """, tuple(event_ids))


def get_event_stats() -> dict:
    """Get event processing statistics."""
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*) AS total_events,
                SUM(CASE WHEN processed = 0 THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) AS processed,
                COUNT(DISTINCT event_type) AS event_types
            FROM {_T()}
        """).fetchone()
        return dict(row) if row else {}


def cleanup_old_events(days: int = 30) -> int:
    """Delete processed events older than N days."""
    with get_conn() as conn:
        if is_oracle():
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE PROCESSED = 1
                  AND CREATED_AT < SYSTIMESTAMP - NUMTODSINTERVAL(:1, 'DAY')
            """, (days,))
        else:
            cur = conn.execute(f"""
                DELETE FROM {_T()}
                WHERE processed = 1
                  AND created_at < datetime('now', ? || ' days')
            """, (f"-{days}",))
        deleted = cur.rowcount
        log.info(f"[EVENTS] Cleaned up {deleted} old events")
        return deleted
