"""
memory.py — Conversation Memory System
Per-user memory with context tracking, entity persistence, and session management.
Phase 8: Sessions persist to Oracle/SQLite via learning/store.py backend.
"""
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("memory")


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

    # Phase 8: Persist after user turn too (best-effort)
    try:
        persist_session(user_id)
    except Exception:
        pass

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

    # Phase 8: Persist after every assistant turn (best-effort, non-blocking)
    try:
        persist_session(user_id)
    except Exception:
        pass

    return session


def get_history_messages(user_id: str, max_turns: int = 10,
                         max_chars: int = 3000) -> list[dict]:
    """Get conversation history with context compression.

    Strategy (short-term + long-term separation):
      - Last 3 turns: full content (short-term, high fidelity)
      - Older turns: compressed summary (long-term, saves tokens)
      - Total budget: max_chars (prevents prompt overflow)

    SQL is never included in history (Phase 10).
    """
    session = get_session(user_id)
    if not session.turns:
        return []

    # Split into recent (full) and older (compressed)
    all_turns = session.turns
    recent_count = min(6, len(all_turns))  # last 3 Q/A pairs = 6 turns
    recent_turns = all_turns[-recent_count:]
    older_turns = all_turns[:-recent_count] if len(all_turns) > recent_count else []

    messages = []

    # Older turns: compress into a single context summary
    if older_turns:
        summary = _summarize_turns(older_turns)
        if summary:
            messages.append({
                "role": "system",
                "content": f"[ملخص المحادثة السابقة: {summary}]"
            })

    # Recent turns: include with content compression
    char_budget = max_chars - sum(len(m.get("content", "")) for m in messages)
    for turn in recent_turns:
        if turn.role == "user":
            content = turn.content[:200]  # cap user messages
            messages.append({"role": "user", "content": content})
        else:
            # Compress assistant responses: first line + row count
            content = _compress_response(turn.content, turn.row_count)
            messages.append({"role": "assistant", "content": content})

        char_budget -= len(messages[-1]["content"])
        if char_budget <= 0:
            break

    # Ensure first message is from user (LLM requirement)
    while messages and messages[0].get("role") == "assistant":
        messages.pop(0)

    return messages


def _summarize_turns(turns: list) -> str:
    """Compress older turns into a brief context summary.
    Extracts: topics discussed, entities referenced, key intents.
    """
    topics = set()
    entities_seen = set()

    for turn in turns:
        if turn.role == "user":
            # Extract topic keywords from user questions
            q = turn.content[:100]
            if turn.intent:
                topics.add(turn.intent.replace("_", " "))
            # Collect entities
            for k, v in turn.entities.items():
                entities_seen.add(f"{k}={v}")
        elif turn.row_count > 0:
            topics.add(f"استعلام ({turn.row_count} نتيجة)")

    parts = []
    if topics:
        parts.append("مواضيع: " + "، ".join(list(topics)[:5]))
    if entities_seen:
        parts.append("سياق: " + "، ".join(list(entities_seen)[:4]))

    return " | ".join(parts) if parts else ""


def _compress_response(content: str, row_count: int) -> str:
    """Compress an assistant response to save tokens.
    Takes first meaningful line + row count indicator.
    """
    if not content:
        return ""
    # Take first line (usually the summary)
    first_line = content.split("\n")[0][:150]
    if row_count > 0:
        return f"({row_count} نتيجة) {first_line}"
    return first_line


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


# ── Session Persistence (removed — AI_CHAT_SESSIONS table dropped) ──

def _ensure_persistence_table() -> bool:
    """No-op — AI_CHAT_SESSIONS table removed; sessions are in-memory only."""
    return False


def persist_session(user_id: str) -> None:
    """No-op — session persistence removed (table dropped)."""
    pass


def load_sessions_from_db(max_load: int = 50) -> int:
    """No-op — AI_CHAT_SESSIONS table removed; always starts fresh."""
    log.debug("[MEMORY] load_sessions_from_db: no DB (in-memory only)")
    return 0
