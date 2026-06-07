"""
erp_actions/store.py — Action Queue, History, and Audit Trail
In-memory store with DB persistence for crash recovery.
"""
import time
import json
import logging
import threading
from typing import Optional
from .models import ActionPlan, ActionStatus, AuditEntry

log = logging.getLogger("erp_actions.store")

# ══════════════════════════════════════════════════════════════════
# In-Memory Store (thread-safe)
# ══════════════════════════════════════════════════════════════════

_actions: dict[str, ActionPlan] = {}       # action_id -> ActionPlan
_user_pending: dict[str, str] = {}         # user_id -> last pending action_id
_audit_log: list[AuditEntry] = []
_lock = threading.Lock()

MAX_ACTIONS = 2000
MAX_AUDIT = 5000
ACTION_TTL = 3600 * 24  # 24 hours


def save_action(plan: ActionPlan) -> None:
    """Save or update an action plan."""
    with _lock:
        _actions[plan.id] = plan
        # Track pending action per user
        if plan.status == ActionStatus.PLANNED.value:
            _user_pending[plan.user_id] = plan.id
        elif plan.user_id in _user_pending and _user_pending[plan.user_id] == plan.id:
            del _user_pending[plan.user_id]
        _cleanup()

    # Persist to DB (non-blocking, best-effort)
    try:
        _persist_action(plan)
    except Exception as e:
        log.debug(f"[ACTION_STORE] Persist failed (non-critical): {e}")


def get_action(action_id: str) -> Optional[ActionPlan]:
    """Get an action by ID."""
    with _lock:
        return _actions.get(action_id)


def get_user_pending(user_id: str) -> Optional[ActionPlan]:
    """Get the pending action for a user (if any)."""
    with _lock:
        action_id = _user_pending.get(user_id)
        if action_id and action_id in _actions:
            plan = _actions[action_id]
            if plan.status == ActionStatus.PLANNED.value:
                return plan
            # Stale: remove
            del _user_pending[user_id]
        return None


def get_pending_actions(user_id: str = "") -> list[dict]:
    """Get all pending actions, optionally filtered by user."""
    with _lock:
        results = []
        for plan in _actions.values():
            if plan.status == ActionStatus.PLANNED.value:
                if not user_id or plan.user_id == user_id:
                    results.append(plan.to_dict())
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results


def get_action_history(
    user_id: str = "",
    limit: int = 50,
    action_type: str = "",
) -> list[dict]:
    """Get action history with optional filters."""
    with _lock:
        results = []
        for plan in _actions.values():
            if plan.status in (ActionStatus.COMPLETED.value,
                               ActionStatus.FAILED.value,
                               ActionStatus.REJECTED.value):
                if user_id and plan.user_id != user_id:
                    continue
                if action_type and plan.action_type != action_type:
                    continue
                results.append(plan.to_dict())
        results.sort(key=lambda x: x.get("executed_at", 0), reverse=True)
        return results[:limit]


def get_action_stats() -> dict:
    """Aggregate action statistics."""
    with _lock:
        total = len(_actions)
        by_status = {}
        by_type = {}
        for plan in _actions.values():
            by_status[plan.status] = by_status.get(plan.status, 0) + 1
            by_type[plan.action_type] = by_type.get(plan.action_type, 0) + 1
        return {
            "total_actions": total,
            "by_status": by_status,
            "by_type": by_type,
            "audit_entries": len(_audit_log),
        }


# ── Audit Trail ──────────────────────────────────────────────────

def add_audit(entry: AuditEntry) -> None:
    """Add an immutable audit entry."""
    with _lock:
        _audit_log.append(entry)
        if len(_audit_log) > MAX_AUDIT:
            _audit_log.pop(0)

    try:
        _persist_audit(entry)
    except Exception as e:
        log.debug(f"[ACTION_STORE] Audit persist failed: {e}")


def get_audit_trail(
    action_id: str = "",
    user_id: str = "",
    limit: int = 100,
) -> list[dict]:
    """Get audit trail with optional filters."""
    with _lock:
        results = []
        for entry in reversed(_audit_log):
            if action_id and entry.action_id != action_id:
                continue
            if user_id and entry.user_id != user_id:
                continue
            results.append({
                "id": entry.id,
                "action_id": entry.action_id,
                "user_id": entry.user_id,
                "action_type": entry.action_type,
                "status_from": entry.status_from,
                "status_to": entry.status_to,
                "detail": entry.detail,
                "sql_executed": entry.sql_executed[:200] if entry.sql_executed else "",
                "timestamp": entry.timestamp,
            })
            if len(results) >= limit:
                break
        return results


# ── Internal ─────────────────────────────────────────────────────

def _cleanup():
    """Remove expired actions and trim store."""
    cutoff = time.time() - ACTION_TTL
    expired = [
        k for k, v in _actions.items()
        if v.created_at < cutoff and v.status not in (
            ActionStatus.PLANNED.value, ActionStatus.EXECUTING.value
        )
    ]
    for k in expired:
        del _actions[k]
    # Trim if still too large
    if len(_actions) > MAX_ACTIONS:
        sorted_actions = sorted(
            _actions.items(),
            key=lambda x: x[1].created_at
        )
        for k, _ in sorted_actions[:len(_actions) - MAX_ACTIONS]:
            if _actions[k].status not in (
                ActionStatus.PLANNED.value, ActionStatus.EXECUTING.value
            ):
                del _actions[k]


# ── DB Persistence removed — action_log / action_audit tables dropped ──

def _persist_action(plan: ActionPlan):
    """Log action plan — no DB (tables removed)."""
    log.info(
        f"[ACTION] id={plan.id} type={plan.action_type} "
        f"status={plan.status} user={plan.user_id}"
    )


def _persist_audit(entry: AuditEntry):
    """Log audit entry — no DB (tables removed)."""
    log.info(
        f"[AUDIT] id={entry.id} action={entry.action_id} "
        f"user={entry.user_id} {entry.status_from}->{entry.status_to} "
        f"detail={str(entry.detail)[:120]}"
    )
