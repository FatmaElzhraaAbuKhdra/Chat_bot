"""
memory.py — Conversation Memory System
Per-user memory with context tracking, entity persistence, and session management.
"""
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConversationTurn:
    role: str                    # user | assistant
    content: str
    timestamp: float = 0.0
    sql: str = ""
    intent: str = ""
    entities: dict = field(default_factory=dict)
    row_count: int = 0


@dataclass
class UserSession:
    user_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    context_entities: dict = field(default_factory=dict)  # persistent entities across turns
    created_at: float = 0.0
    last_active: float = 0.0
    query_count: int = 0

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_active:
            self.last_active = now


# ── Session store ─────────────────────────────────────────────────
_sessions: dict[str, UserSession] = {}
MAX_TURNS = 20              # per user
MAX_SESSIONS = 500          # total
SESSION_TTL = 3600 * 4      # 4 hours


def get_session(user_id: str) -> UserSession:
    """Get or create a user session."""
    _cleanup_stale()
    if user_id not in _sessions:
        _sessions[user_id] = UserSession(user_id=user_id)
    session = _sessions[user_id]
    session.last_active = time.time()
    return session


def add_user_turn(user_id: str, question: str, entities: dict = None, intent: str = "") -> UserSession:
    """Record a user message in the session."""
    session = get_session(user_id)
    turn = ConversationTurn(
        role="user",
        content=question,
        timestamp=time.time(),
        intent=intent,
        entities=entities or {},
    )
    session.turns.append(turn)

    # Merge entities into persistent context
    if entities:
        session.context_entities.update(entities)

    _trim_session(session)
    return session


def add_assistant_turn(user_id: str, answer: str, sql: str = "",
                       row_count: int = 0, entities: dict = None) -> UserSession:
    """Record an assistant response in the session."""
    session = get_session(user_id)
    turn = ConversationTurn(
        role="assistant",
        content=answer,
        timestamp=time.time(),
        sql=sql,
        row_count=row_count,
        entities=entities or {},
    )
    session.turns.append(turn)
    session.query_count += 1
    _trim_session(session)
    return session


def get_history_messages(user_id: str, max_turns: int = 10) -> list[dict]:
    """Get conversation history as messages list for LLM context."""
    session = get_session(user_id)
    recent = session.turns[-max_turns * 2:] if len(session.turns) > max_turns * 2 else session.turns

    messages = []
    for turn in recent:
        if turn.role == "user":
            messages.append({"role": "user", "content": turn.content})
        else:
            # Include SQL result summary for context
            content = turn.content
            if turn.sql:
                content = f"SQL: {turn.sql}\n({turn.row_count} rows)\n{content}"
            messages.append({"role": "assistant", "content": content})

    # Ensure first message is from user
    while messages and messages[0].get("role") == "assistant":
        messages.pop(0)

    return messages


def get_context_entities(user_id: str) -> dict:
    """Get persistent entities from the conversation context."""
    session = get_session(user_id)
    return dict(session.context_entities)


def clear_session(user_id: str):
    """Clear a user's session."""
    if user_id in _sessions:
        del _sessions[user_id]


def get_session_stats() -> dict:
    """Return memory system stats."""
    return {
        "active_sessions": len(_sessions),
        "total_turns": sum(len(s.turns) for s in _sessions.values()),
        "total_queries": sum(s.query_count for s in _sessions.values()),
    }


# ── Internal ──────────────────────────────────────────────────────

def _trim_session(session: UserSession):
    """Trim session to max turns."""
    if len(session.turns) > MAX_TURNS * 2:
        session.turns = session.turns[-(MAX_TURNS * 2):]


def _cleanup_stale():
    """Remove stale sessions."""
    now = time.time()
    stale = [uid for uid, s in _sessions.items()
             if now - s.last_active > SESSION_TTL]
    for uid in stale:
        del _sessions[uid]

    if len(_sessions) > MAX_SESSIONS:
        sorted_sessions = sorted(_sessions.items(), key=lambda x: x[1].last_active)
        for uid, _ in sorted_sessions[:len(_sessions) - MAX_SESSIONS]:
            del _sessions[uid]
