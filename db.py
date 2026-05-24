import asyncio
import logging
import oracledb
import os

log = logging.getLogger("db")

DB_QUERY_TIMEOUT = 30  # seconds
DB_MAX_RETRIES = 2     # retry transient failures
DB_RETRY_BASE_DELAY = 1.0  # seconds (exponential: 1s, 2s)

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            dsn=f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_SID')}",
            min=2, max=10, increment=1
        )
    return _pool


def _clean_sql(sql: str) -> str:
    import re
    sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"```\s*", "", sql)
    sql = sql.strip().rstrip(";").strip()
    # Strip bind variables — replace :variable with NULL to prevent DPY-4010
    sql = re.sub(r':(?!=)([a-zA-Z_]\w*)', 'NULL', sql)
    return sql


def has_bind_variables(sql: str) -> bool:
    """Check if SQL contains :bind_variable patterns (but not := which is PL/SQL)."""
    import re
    return bool(re.search(r':(?!=)\b[a-zA-Z_]\w*', sql))


def _run_query_sync(sql: str, params: dict = None) -> list[dict]:
    """Synchronous query execution (runs in thread pool via asyncio)."""
    pool_sync = _pool
    with pool_sync.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchmany(501)
            truncated = len(rows) > 500
            result = [dict(zip(cols, row)) for row in rows[:500]]
            if truncated:
                result.append({"__truncated__": True, "__limit__": 500})
            return result


def _is_transient_error(e: Exception) -> bool:
    """Check if a DB error is transient and worth retrying."""
    err = str(e).lower()
    transient_signals = [
        "ora-03113",  # end-of-file on communication channel
        "ora-03114",  # not connected to oracle
        "ora-03135",  # connection lost
        "ora-12170",  # connect timeout
        "ora-12571",  # packet writer failure
        "ora-25408",  # can not safely replay
        "dpy-4011",   # the database or network closed the connection
        "dpy-4027",   # no connection to the database
        "connection",
        "broken pipe",
        "timed out",
    ]
    return any(sig in err for sig in transient_signals)


async def execute_query(sql: str, params: dict = None) -> list[dict]:
    """ينفّذ SQL ويرجع list of dicts — الحد الأقصى 500 صف — timeout 30s — retry on transient"""
    sql = _clean_sql(sql)
    await get_pool()

    last_err = None
    for attempt in range(1 + DB_MAX_RETRIES):
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _run_query_sync, sql, params),
                timeout=DB_QUERY_TIMEOUT,
            )
            return result
        except asyncio.TimeoutError:
            log.warning(f"[DB] Query timeout ({DB_QUERY_TIMEOUT}s), attempt {attempt+1}: {sql[:100]}...")
            last_err = TimeoutError(f"انتهت مهلة الاستعلام ({DB_QUERY_TIMEOUT} ثانية)")
            if attempt < DB_MAX_RETRIES:
                await asyncio.sleep(DB_RETRY_BASE_DELAY * (2 ** attempt))
                continue
        except Exception as e:
            if _is_transient_error(e) and attempt < DB_MAX_RETRIES:
                delay = DB_RETRY_BASE_DELAY * (2 ** attempt)
                log.warning(f"[DB] Transient error, retry {attempt+1}/{DB_MAX_RETRIES} in {delay}s: {e}")
                last_err = e
                await asyncio.sleep(delay)
                continue
            raise

    raise last_err
