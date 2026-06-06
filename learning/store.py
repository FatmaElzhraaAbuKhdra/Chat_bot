"""
learning/store.py — Unified Storage Backend (Oracle-first, SQLite fallback)
Production: Oracle via shared connection pool from db.py
Development: SQLite file-based for zero-config local testing.
"""
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

log = logging.getLogger("learning.store")

# ── Configuration ──────────────────────────────────────────────────
_BACKEND = None          # "oracle" | "sqlite" — set on init
_SQLITE_PATH = Path(__file__).parent.parent / "data" / "learning.db"
_PFX = "AI_"             # Oracle table prefix

# ═══════════════════════════════════════════════════════════════════
# Connection Management
# ═══════════════════════════════════════════════════════════════════

def _detect_backend() -> str:
    """Auto-detect: Oracle if pool exists, else SQLite."""
    if os.getenv("LEARNING_FORCE_SQLITE", "").lower() in ("1", "true", "yes"):
        return "sqlite"
    try:
        import oracledb
        dsn = f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_SID')}"
        conn = oracledb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            dsn=dsn
        )
        conn.close()
        return "oracle"
    except Exception:
        return "sqlite"


def get_backend() -> str:
    """Return current backend name."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _detect_backend()
    return _BACKEND


class OracleRow(dict):
    """Dict subclass that supports both dict[key] and dict.key access."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


@contextmanager
def get_conn():
    """
    Unified connection context manager.
    Oracle: acquires from shared connection pool (db.py), returns dict-like rows.
    SQLite: opens file connection with Row factory.
    """
    backend = get_backend()

    if backend == "oracle":
        # Reuse the shared connection pool from db.py (initialized at startup)
        from db import _pool as _shared_pool
        if _shared_pool is None:
            # Fallback: create a direct connection if pool not yet initialized
            import oracledb
            dsn = f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_SID')}"
            conn = oracledb.connect(
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                dsn=dsn
            )
            try:
                yield _OracleConnWrapper(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return

        conn = _shared_pool.acquire()
        try:
            yield _OracleConnWrapper(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _shared_pool.release(conn)
    else:
        conn = sqlite3.connect(str(_get_sqlite_path()), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class _OracleConnWrapper:
    """Wraps an Oracle connection so .execute() returns dict rows like SQLite."""

    def __init__(self, conn):
        self._conn = conn
        self._cursor = None

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        if params is None:
            cur.execute(sql)
        elif isinstance(params, dict):
            # Auto-set CLOB type for long string values
            try:
                import oracledb
                sizes = {k: oracledb.DB_TYPE_CLOB
                         for k, v in params.items()
                         if isinstance(v, str) and len(v) > 32000}
                if sizes:
                    cur.setinputsizes(**sizes)
            except Exception:
                pass
            cur.execute(sql, params)
        elif isinstance(params, (tuple, list)):
            param_list = list(params)
            # Auto-set CLOB type for long string values (positional)
            try:
                import oracledb
                sizes = [oracledb.DB_TYPE_CLOB if isinstance(p, str) and len(p) > 32000
                         else None for p in param_list]
                if any(s for s in sizes):
                    cur.setinputsizes(*sizes)
            except Exception:
                pass
            cur.execute(sql, param_list)
        else:
            cur.execute(sql, params)
        self._cursor = cur
        return _OracleCursorWrapper(cur)

    def executemany(self, sql: str, data):
        cur = self._conn.cursor()
        cur.executemany(sql, data)
        self._cursor = cur
        return cur

    def executescript(self, script: str):
        """Execute multiple SQL statements separated by semicolons."""
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    self.execute(stmt)
                except Exception:
                    pass

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class _OracleCursorWrapper:
    """Wraps Oracle cursor to return dict rows."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return getattr(self._cursor, 'lastrowid', None)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def _row_to_dict(self, row):
        if row is None:
            return None
        cols = [d[0].lower() for d in self._cursor.description]
        return OracleRow(zip(cols, row))

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._row_to_dict(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows or not self._cursor.description:
            return []
        cols = [d[0].lower() for d in self._cursor.description]
        return [OracleRow(zip(cols, r)) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        if not rows or not self._cursor.description:
            return []
        cols = [d[0].lower() for d in self._cursor.description]
        return [OracleRow(zip(cols, r)) for r in rows]


def _get_sqlite_path() -> Path:
    custom = os.getenv("LEARNING_DB_PATH")
    if custom:
        return Path(custom)
    return _SQLITE_PATH


# ═══════════════════════════════════════════════════════════════════
# Schema Initialization
# ═══════════════════════════════════════════════════════════════════

def init_learning_db() -> None:
    """Initialize learning database — Oracle or SQLite based on backend."""
    global _BACKEND
    _BACKEND = _detect_backend()

    if _BACKEND == "oracle":
        _init_oracle()
    else:
        _init_sqlite()

    log.info(f"[STORE] Backend: {_BACKEND}")


def _init_oracle():
    """Create AI_ tables in Oracle if they don't exist."""
    created = 0
    with get_conn() as conn:
        # Check existing tables
        existing_rows = conn.execute(
            "SELECT table_name FROM user_tables WHERE table_name LIKE :p",
            {"p": f"{_PFX}%"}
        ).fetchall()
        existing = {r["table_name"] for r in existing_rows}

        for table_name, ddl in _ORACLE_TABLES.items():
            if table_name not in existing:
                try:
                    conn.execute(ddl)
                    created += 1
                    log.info(f"[STORE] Created Oracle table {table_name}")
                except Exception as e:
                    log.warning(f"[STORE] Failed to create {table_name}: {e}")

        # Create indexes (ignore if exists)
        for idx_sql in _ORACLE_INDEXES:
            try:
                conn.execute(idx_sql)
            except Exception:
                pass  # already exists

    log.info(f"[STORE] Oracle init: {created} new tables, "
             f"{len(existing)} already existed")


def _init_sqlite():
    """Create SQLite learning database."""
    db_path = _get_sqlite_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.executescript(_SQLITE_SCHEMA)
    conn.commit()
    conn.close()
    log.info(f"[STORE] SQLite initialized at {db_path}")


# ═══════════════════════════════════════════════════════════════════
# Oracle Table Definitions
# ═══════════════════════════════════════════════════════════════════

_ORACLE_TABLES = {
    f"{_PFX}FEEDBACK": f"""
CREATE TABLE {_PFX}FEEDBACK (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    USER_ID         VARCHAR2(100) NOT NULL,
    QUESTION        NVARCHAR2(2000) NOT NULL,
    CATEGORY        VARCHAR2(50),
    DOMAIN          VARCHAR2(50),
    SUB_INTENT      VARCHAR2(100),
    TEMPLATE_USED   VARCHAR2(100),
    SQL_GENERATED   CLOB,
    AI_RESPONSE     NCLOB,
    FEEDBACK_TYPE   VARCHAR2(20) NOT NULL,
    CORRECTED_RESPONSE NCLOB,
    CORRECTED_SQL   CLOB,
    USER_REPHRASED  NVARCHAR2(2000),
    RATING          NUMBER(1),
    NOTES           NVARCHAR2(1000)
)""",

    f"{_PFX}TEMPLATE_STATS": f"""
CREATE TABLE {_PFX}TEMPLATE_STATS (
    TEMPLATE_NAME   VARCHAR2(100) PRIMARY KEY,
    TOTAL_USES      NUMBER DEFAULT 0,
    SUCCESS_COUNT   NUMBER DEFAULT 0,
    FAILURE_COUNT   NUMBER DEFAULT 0,
    ZERO_RESULT_COUNT NUMBER DEFAULT 0,
    AVG_EXEC_MS     NUMBER(10,2) DEFAULT 0,
    LAST_USED       TIMESTAMP,
    USER_APPROVALS  NUMBER DEFAULT 0,
    USER_REJECTIONS NUMBER DEFAULT 0
)""",

    f"{_PFX}SYNONYMS": f"""
CREATE TABLE {_PFX}SYNONYMS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TERM            NVARCHAR2(200) NOT NULL,
    CANONICAL       VARCHAR2(200) NOT NULL,
    DOMAIN          VARCHAR2(50),
    SUB_INTENT      VARCHAR2(100),
    CONFIDENCE      NUMBER(3,2) DEFAULT 0.8,
    SOURCE          VARCHAR2(30) DEFAULT 'learned',
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    USAGE_COUNT     NUMBER DEFAULT 0,
    CONSTRAINT UQ_SYN UNIQUE (TERM, CANONICAL)
)""",

    f"{_PFX}LEARNED_PATTERNS": f"""
CREATE TABLE {_PFX}LEARNED_PATTERNS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    QUESTION        NVARCHAR2(2000) NOT NULL,
    SUB_INTENT      VARCHAR2(100) NOT NULL,
    DOMAIN          VARCHAR2(50),
    ENTITIES_JSON   CLOB,
    CONFIDENCE      NUMBER(3,2) DEFAULT 0.8,
    SOURCE          VARCHAR2(30) DEFAULT 'feedback',
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    USAGE_COUNT     NUMBER DEFAULT 0,
    SUCCESS_COUNT   NUMBER DEFAULT 0
)""",

    f"{_PFX}ANALYTICS_PREFS": f"""
CREATE TABLE {_PFX}ANALYTICS_PREFS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    USER_ID         VARCHAR2(100),
    QUERY_TYPE      VARCHAR2(100) NOT NULL,
    PREFERRED_CHART VARCHAR2(30),
    PREFERRED_LIMIT NUMBER,
    USAGE_COUNT     NUMBER DEFAULT 1,
    LAST_USED       TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT UQ_APREFS UNIQUE (USER_ID, QUERY_TYPE)
)""",

    f"{_PFX}WORKFLOW_PATTERNS": f"""
CREATE TABLE {_PFX}WORKFLOW_PATTERNS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SEQUENCE_JSON   CLOB NOT NULL,
    SEQUENCE_HASH   VARCHAR2(64) UNIQUE,
    FREQUENCY       NUMBER DEFAULT 1,
    AVG_GAP_SECONDS NUMBER(10,2),
    LAST_SEEN       TIMESTAMP DEFAULT SYSTIMESTAMP
)""",

    f"{_PFX}ERP_KNOWLEDGE": f"""
CREATE TABLE {_PFX}ERP_KNOWLEDGE (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CONCEPT         VARCHAR2(200) NOT NULL UNIQUE,
    DESCRIPTION_AR  NCLOB,
    DESCRIPTION_EN  CLOB,
    DOMAIN          VARCHAR2(50),
    TABLES_JSON     CLOB,
    COLUMNS_JSON    CLOB,
    TERMS_AR_JSON   NCLOB,
    TERMS_EN_JSON   CLOB,
    SQL_PATTERNS    CLOB,
    SOURCE          VARCHAR2(30) DEFAULT 'manual',
    CONFIDENCE      NUMBER(3,2) DEFAULT 1.0,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",

    f"{_PFX}EMBEDDINGS_CACHE": f"""
CREATE TABLE {_PFX}EMBEDDINGS_CACHE (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TEXT_CONTENT    NCLOB NOT NULL,
    TEXT_HASH       VARCHAR2(64) UNIQUE,
    EMBEDDING_BLOB  BLOB,
    CATEGORY        VARCHAR2(30),
    METADATA_JSON   CLOB,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",

    f"{_PFX}EVENTS": f"""
CREATE TABLE {_PFX}EVENTS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    EVENT_TYPE      VARCHAR2(50) NOT NULL,
    EVENT_DATA      CLOB,
    USER_ID         VARCHAR2(100),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    PROCESSED       NUMBER(1) DEFAULT 0
)""",

    f"{_PFX}ONTOLOGY_NODES": f"""
CREATE TABLE {_PFX}ONTOLOGY_NODES (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NODE_KEY        VARCHAR2(100) NOT NULL UNIQUE,
    NODE_TYPE       VARCHAR2(30) NOT NULL,
    LABEL_AR        NVARCHAR2(200),
    LABEL_EN        VARCHAR2(200),
    DOMAIN          VARCHAR2(50),
    METADATA_JSON   CLOB,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",

    f"{_PFX}ONTOLOGY_EDGES": f"""
CREATE TABLE {_PFX}ONTOLOGY_EDGES (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SOURCE_KEY      VARCHAR2(100) NOT NULL,
    TARGET_KEY      VARCHAR2(100) NOT NULL,
    RELATION        VARCHAR2(50) NOT NULL,
    WEIGHT          NUMBER(3,2) DEFAULT 1.0,
    METADATA_JSON   CLOB,
    CONSTRAINT UQ_EDGE UNIQUE (SOURCE_KEY, TARGET_KEY, RELATION)
)""",

    f"{_PFX}BI_CONTEXT": f"""
CREATE TABLE {_PFX}BI_CONTEXT (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SESSION_ID      VARCHAR2(100) NOT NULL,
    USER_ID         VARCHAR2(100),
    CONTEXT_JSON    CLOB NOT NULL,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    EXPIRES_AT      TIMESTAMP
)""",

    f"{_PFX}METRICS": f"""
CREATE TABLE {_PFX}METRICS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    METRIC_NAME     VARCHAR2(100) NOT NULL,
    METRIC_VALUE    NUMBER(15,4),
    DIMENSION       VARCHAR2(100),
    RECORDED_AT     TIMESTAMP DEFAULT SYSTIMESTAMP
)""",

    f"{_PFX}VIZ_RULES": f"""
CREATE TABLE {_PFX}VIZ_RULES (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    RULE_KEY        VARCHAR2(100) NOT NULL UNIQUE,
    DOMAIN          VARCHAR2(50),
    SUB_INTENT      VARCHAR2(100),
    DATA_SHAPE      VARCHAR2(30),
    BEST_CHART      VARCHAR2(30),
    SCORE           NUMBER(5,2) DEFAULT 0,
    USAGE_COUNT     NUMBER DEFAULT 0,
    FEEDBACK_SCORE  NUMBER(3,2) DEFAULT 0,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",
    "alert_snapshot": f"""
CREATE TABLE {_PFX}ALERT_SNAPSHOT (
    SNAPSHOT_KEY    VARCHAR2(50) PRIMARY KEY,
    SNAPSHOT_DATA   CLOB,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",
    "action_log": f"""
CREATE TABLE {_PFX}ACTION_LOG (
    ACTION_ID       VARCHAR2(32) PRIMARY KEY,
    ACTION_TYPE     VARCHAR2(50) NOT NULL,
    STATUS          VARCHAR2(20) NOT NULL,
    USER_ID         VARCHAR2(100),
    ACTION_DATA     CLOB,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",
    "action_audit": f"""
CREATE TABLE {_PFX}ACTION_AUDIT (
    AUDIT_ID        VARCHAR2(24) PRIMARY KEY,
    ACTION_ID       VARCHAR2(32) NOT NULL,
    USER_ID         VARCHAR2(100),
    ACTION_TYPE     VARCHAR2(50),
    STATUS_FROM     VARCHAR2(20),
    STATUS_TO       VARCHAR2(20),
    DETAIL          VARCHAR2(1000),
    SQL_EXECUTED    VARCHAR2(2000),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
)""",
}

_ORACLE_INDEXES = [
    f"CREATE INDEX IDX_{_PFX}FB_SUB ON {_PFX}FEEDBACK(SUB_INTENT)",
    f"CREATE INDEX IDX_{_PFX}FB_TYPE ON {_PFX}FEEDBACK(FEEDBACK_TYPE)",
    f"CREATE INDEX IDX_{_PFX}FB_DATE ON {_PFX}FEEDBACK(CREATED_AT)",
    f"CREATE INDEX IDX_{_PFX}SYN_TERM ON {_PFX}SYNONYMS(TERM)",
    f"CREATE INDEX IDX_{_PFX}LP_SUB ON {_PFX}LEARNED_PATTERNS(SUB_INTENT)",
    f"CREATE INDEX IDX_{_PFX}EMB_CAT ON {_PFX}EMBEDDINGS_CACHE(CATEGORY)",
    f"CREATE INDEX IDX_{_PFX}EVT_TYPE ON {_PFX}EVENTS(EVENT_TYPE, PROCESSED)",
    f"CREATE INDEX IDX_{_PFX}ON_KEY ON {_PFX}ONTOLOGY_NODES(NODE_TYPE, DOMAIN)",
    f"CREATE INDEX IDX_{_PFX}OE_SRC ON {_PFX}ONTOLOGY_EDGES(SOURCE_KEY)",
    f"CREATE INDEX IDX_{_PFX}OE_TGT ON {_PFX}ONTOLOGY_EDGES(TARGET_KEY)",
    f"CREATE INDEX IDX_{_PFX}BI_SES ON {_PFX}BI_CONTEXT(SESSION_ID)",
    f"CREATE INDEX IDX_{_PFX}MET_NAME ON {_PFX}METRICS(METRIC_NAME, RECORDED_AT)",
    f"CREATE INDEX IDX_{_PFX}VIZ_DOM ON {_PFX}VIZ_RULES(DOMAIN, SUB_INTENT)",
]


# ═══════════════════════════════════════════════════════════════════
# SQLite Schema (fallback)
# ═══════════════════════════════════════════════════════════════════

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT DEFAULT (datetime('now')),
    user_id         TEXT NOT NULL,
    question        TEXT NOT NULL,
    category        TEXT,
    domain          TEXT,
    sub_intent      TEXT,
    template_used   TEXT,
    sql_generated   TEXT,
    ai_response     TEXT,
    feedback_type   TEXT NOT NULL,
    corrected_response TEXT,
    corrected_sql   TEXT,
    user_rephrased  TEXT,
    rating          INTEGER,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_sub ON feedback(sub_intent);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);

CREATE TABLE IF NOT EXISTS template_stats (
    template_name   TEXT PRIMARY KEY,
    total_uses      INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    zero_result_count INTEGER DEFAULT 0,
    avg_exec_ms     REAL DEFAULT 0,
    last_used       TEXT,
    user_approvals  INTEGER DEFAULT 0,
    user_rejections INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS synonyms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    term            TEXT NOT NULL,
    canonical       TEXT NOT NULL,
    domain          TEXT,
    sub_intent      TEXT,
    confidence      REAL DEFAULT 0.8,
    source          TEXT DEFAULT 'learned',
    created_at      TEXT DEFAULT (datetime('now')),
    usage_count     INTEGER DEFAULT 0,
    UNIQUE(term, canonical)
);
CREATE INDEX IF NOT EXISTS idx_syn_term ON synonyms(term);

CREATE TABLE IF NOT EXISTS learned_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question        TEXT NOT NULL,
    sub_intent      TEXT NOT NULL,
    domain          TEXT,
    entities_json   TEXT,
    confidence      REAL DEFAULT 0.8,
    source          TEXT DEFAULT 'feedback',
    created_at      TEXT DEFAULT (datetime('now')),
    usage_count     INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_lp_sub ON learned_patterns(sub_intent);

CREATE TABLE IF NOT EXISTS analytics_prefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT,
    query_type      TEXT NOT NULL,
    preferred_chart TEXT,
    preferred_limit INTEGER,
    usage_count     INTEGER DEFAULT 1,
    last_used       TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, query_type)
);

CREATE TABLE IF NOT EXISTS workflow_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_json   TEXT NOT NULL,
    sequence_hash   TEXT UNIQUE,
    frequency       INTEGER DEFAULT 1,
    avg_gap_seconds REAL,
    last_seen       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS erp_knowledge (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    concept         TEXT NOT NULL UNIQUE,
    description_ar  TEXT,
    description_en  TEXT,
    domain          TEXT,
    tables_json     TEXT,
    columns_json    TEXT,
    terms_ar_json   TEXT,
    terms_en_json   TEXT,
    sql_patterns    TEXT,
    source          TEXT DEFAULT 'manual',
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS embeddings_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text_content    TEXT NOT NULL,
    text_hash       TEXT UNIQUE,
    embedding_json  TEXT NOT NULL,
    category        TEXT,
    metadata_json   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_emb_cat ON embeddings_cache(category);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    event_data      TEXT,
    user_id         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    processed       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_evt_type ON events(event_type, processed);

CREATE TABLE IF NOT EXISTS ontology_nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_key        TEXT NOT NULL UNIQUE,
    node_type       TEXT NOT NULL,
    label_ar        TEXT,
    label_en        TEXT,
    domain          TEXT,
    metadata_json   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_on_key ON ontology_nodes(node_type, domain);

CREATE TABLE IF NOT EXISTS ontology_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key      TEXT NOT NULL,
    target_key      TEXT NOT NULL,
    relation        TEXT NOT NULL,
    weight          REAL DEFAULT 1.0,
    metadata_json   TEXT,
    UNIQUE(source_key, target_key, relation)
);
CREATE INDEX IF NOT EXISTS idx_oe_src ON ontology_edges(source_key);
CREATE INDEX IF NOT EXISTS idx_oe_tgt ON ontology_edges(target_key);

CREATE TABLE IF NOT EXISTS bi_context (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    user_id         TEXT,
    context_json    TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    expires_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bi_ses ON bi_context(session_id);

CREATE TABLE IF NOT EXISTS metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name     TEXT NOT NULL,
    metric_value    REAL,
    dimension       TEXT,
    recorded_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_met_name ON metrics(metric_name, recorded_at);

CREATE TABLE IF NOT EXISTS viz_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key        TEXT NOT NULL UNIQUE,
    domain          TEXT,
    sub_intent      TEXT,
    data_shape      TEXT,
    best_chart      TEXT,
    score           REAL DEFAULT 0,
    usage_count     INTEGER DEFAULT 0,
    feedback_score  REAL DEFAULT 0,
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_viz_dom ON viz_rules(domain, sub_intent);

CREATE TABLE IF NOT EXISTS alert_snapshot (
    snapshot_key    TEXT PRIMARY KEY,
    snapshot_data   TEXT,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS action_log (
    action_id       TEXT PRIMARY KEY,
    action_type     TEXT NOT NULL,
    status          TEXT NOT NULL,
    user_id         TEXT,
    action_data     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS action_audit (
    audit_id        TEXT PRIMARY KEY,
    action_id       TEXT NOT NULL,
    user_id         TEXT,
    action_type     TEXT,
    status_from     TEXT,
    status_to       TEXT,
    detail          TEXT,
    sql_executed    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_aa_action ON action_audit(action_id);
"""


# ═══════════════════════════════════════════════════════════════════
# SQL Helpers — backend-agnostic
# ═══════════════════════════════════════════════════════════════════

def is_oracle() -> bool:
    return get_backend() == "oracle"


def tbl(name: str) -> str:
    """Return table name with prefix for Oracle, plain for SQLite."""
    if is_oracle():
        return f"{_PFX}{name.upper()}"
    return name.lower()


def now_expr() -> str:
    """Return current-timestamp expression for active backend."""
    return "SYSTIMESTAMP" if is_oracle() else "datetime('now')"


def param(name: str) -> str:
    """Return parameter placeholder: :name for Oracle, ? for SQLite."""
    return f":{name}" if is_oracle() else "?"


def params_dict(*values, **named) -> dict | tuple:
    """
    Build params for the active backend.
    Oracle: returns dict with named keys.
    SQLite: returns tuple of positional values.
    """
    if is_oracle():
        return named
    return values if values else tuple(named.values())
