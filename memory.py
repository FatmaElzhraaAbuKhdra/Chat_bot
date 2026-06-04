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


# ── Phase 8: Persistence Layer ───────────────────────────────────
_PERSIST_TABLE = "CHAT_SESSIONS"
_persistence_ready = False


def _ensure_persistence_table():
    """Create persistence table if needed (called once)."""
    global _persistence_ready
    if _persistence_ready:
        return True
    try:
        from learning.store import get_conn, get_backend, is_oracle, tbl
        with get_conn() as conn:
            if is_oracle():
                # Check if table exists
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM user_tables WHERE table_name = :1",
                    ("AI_CHAT_SESSIONS",)
                ).fetchone()
                if not row or row["cnt"] == 0:
                    conn.execute(f"""
                        CREATE TABLE AI_CHAT_SESSIONS (
                            SESSION_ID   VARCHAR2(100) PRIMARY KEY,
                            USER_ID      VARCHAR2(100) NOT NULL,
                            TURNS_JSON   CLOB,
                            ENTITIES_JSON CLOB,
                            QUERY_COUNT  NUMBER DEFAULT 0,
                            CREATED_AT   NUMBER,
                            LAST_ACTIVE  NUMBER,
                            UPDATED_AT   TIMESTAMP DEFAULT SYSTIMESTAMP
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IDX_AI_CS_USER ON AI_CHAT_SESSIONS(USER_ID)"
                    )
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id   TEXT PRIMARY KEY,
                        user_id      TEXT NOT NULL,
                        turns_json   TEXT,
                        entities_json TEXT,
                        query_count  INTEGER DEFAULT 0,
                        created_at   REAL,
                        last_active  REAL,
                        updated_at   TEXT DEFAULT (datetime('now'))
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cs_user ON chat_sessions(user_id)"
                )
        _persistence_ready = True
        return True
    except Exception as e:
        log.debug(f"[MEMORY] Persistence table setup failed: {e}")
        return False


def persist_session(user_id: str):
    """Save current session to database (non-blocking, best-effort)."""
    if user_id not in _sessions:
        return
    if not _ensure_persistence_table():
        return
    try:
        from learning.store import get_conn, is_oracle
        session = _sessions[user_id]

        # Serialize turns (last 20 only to limit storage)
        turns_data = []
        for t in session.turns[-MAX_TURNS * 2:]:
            turns_data.append({
                "role": t.role,
                "content": t.content[:500],  # truncate long content
                "ts": t.timestamp,
                "intent": t.intent,
                "entities": t.entities,
                "row_count": t.row_count,
            })
        turns_json = json.dumps(turns_data, ensure_ascii=False)
        entities_json = json.dumps(session.context_entities, ensure_ascii=False)

        with get_conn() as conn:
            if is_oracle():
                conn.execute(f"""
                    MERGE INTO AI_CHAT_SESSIONS t
                    USING (SELECT :1 AS sid FROM DUAL) s
                    ON (t.SESSION_ID = s.sid)
                    WHEN MATCHED THEN UPDATE SET
                        TURNS_JSON = :2, ENTITIES_JSON = :3,
                        QUERY_COUNT = :4, LAST_ACTIVE = :5,
                        UPDATED_AT = SYSTIMESTAMP
                    WHEN NOT MATCHED THEN INSERT
                        (SESSION_ID, USER_ID, TURNS_JSON, ENTITIES_JSON,
                         QUERY_COUNT, CREATED_AT, LAST_ACTIVE)
                    VALUES (:6, :7, :8, :9, :10, :11, :12)
                """, (
                    user_id, turns_json, entities_json,
                    session.query_count, session.last_active,
                    user_id, user_id, turns_json, entities_json,
                    session.query_count, session.created_at, session.last_active,
                ))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO chat_sessions
                        (session_id, user_id, turns_json, entities_json,
                         query_count, created_at, last_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, user_id, turns_json, entities_json,
                    session.query_count, session.created_at, session.last_active,
                ))
        log.debug(f"[MEMORY] Persisted session user={user_id} "
                  f"turns={len(turns_data)} entities={len(session.context_entities)}")
    except Exception as e:
        log.warning(f"[MEMORY] persist_session failed for user={user_id}: {e}")


def load_sessions_from_db(max_load: int = 50) -> int:
    """Load recent sessions from database on startup.
    Called from app.py startup to restore sessions that survived a restart.
    Returns number of sessions loaded.
    """
    if not _ensure_persistence_table():
        log.info("[MEMORY] Persistence table not ready — skipping session restore")
        return 0
    loaded = 0
    try:
        from learning.store import get_conn, is_oracle
        with get_conn() as conn:
            if is_oracle():
                rows = conn.execute(f"""
                    SELECT SESSION_ID, USER_ID, TURNS_JSON, ENTITIES_JSON,
                           QUERY_COUNT, CREATED_AT, LAST_ACTIVE
                    FROM AI_CHAT_SESSIONS
                    WHERE LAST_ACTIVE > :1
                    ORDER BY LAST_ACTIVE DESC
                    FETCH FIRST :2 ROWS ONLY
                """, (time.time() - SESSION_TTL, max_load)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT session_id, user_id, turns_json, entities_json,
                           query_count, created_at, last_active
                    FROM chat_sessions
                    WHERE last_active > ?
                    ORDER BY last_active DESC
                    LIMIT ?
                """, (time.time() - SESSION_TTL, max_load)).fetchall()

        for row in rows:
            row = dict(row)  # ROW SAFETY: OracleRow/sqlite3.Row → dict (no row-type assumption)
            uid = row["user_id"]
            if uid in _sessions:
                continue  # don't overwrite active session

            turns_json = row["turns_json"]
            entities_json = row["entities_json"]
            query_count = row["query_count"]
            created_at = row["created_at"]
            last_active = row["last_active"]

            # Rebuild session
            session = UserSession(
                user_id=uid,
                created_at=float(created_at or 0),
                last_active=float(last_active or 0),
                query_count=int(query_count or 0),
            )

            # Restore entities
            if entities_json:
                try:
                    session.context_entities = json.loads(entities_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Restore turns
            if turns_json:
                try:
                    turns_data = json.loads(turns_json)
                    for td in turns_data:
                        session.turns.append(ConversationTurn(
                            role=td.get("role", "user"),
                            content=td.get("content", ""),
                            timestamp=td.get("ts", 0),
                            intent=td.get("intent", ""),
                            entities=td.get("entities", {}),
                            row_count=td.get("row_count", 0),
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass

            _sessions[uid] = session
            loaded += 1

        log.info(f"[MEMORY] Startup restore: loaded {loaded} sessions "
                 f"(total turns={sum(len(s.turns) for s in _sessions.values())})")
    except Exception as e:
        log.warning(f"[MEMORY] load_sessions_from_db failed: {e}")
    return loaded
