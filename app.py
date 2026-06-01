import os
import sys
import io
import time
import logging
import asyncio
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from routers import chat, widget, upload, learning as learning_router, proactive as proactive_router
from routers import actions as actions_router, exports as exports_router
from routers import stream as stream_router
from schema_loader import init_schema_context
from cache import get_all_stats as get_cache_stats, invalidate_all as invalidate_cache, cleanup_all_expired

load_dotenv()

log = logging.getLogger("app")

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="JustClick AI Chatbot", version="1.0")

_startup_time = time.time()


# ── Security Headers Middleware ──────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # CSP: allow self, inline styles/scripts (needed for SPA), Chart.js CDN
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Rate Limiting Middleware ─────────────────────────────────────
_RATE_LIMIT_CHAT = int(os.getenv("RATE_LIMIT_CHAT", "30"))       # requests per minute
_RATE_LIMIT_LEARNING = int(os.getenv("RATE_LIMIT_LEARNING", "60"))  # requests per minute
_rate_store: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limiter for /chat and /learning endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        client_ip = request.client.host if request.client else "unknown"

        # Determine rate limit based on path
        limit = 0
        if path.startswith("/chat"):
            limit = _RATE_LIMIT_CHAT
        elif path.startswith("/learning"):
            limit = _RATE_LIMIT_LEARNING

        if limit > 0:
            now = time.time()
            key = f"{client_ip}:{path.split('/')[1]}"
            window = _rate_store[key]

            # Purge entries older than 60 seconds
            _rate_store[key] = [t for t in window if now - t < 60]
            window = _rate_store[key]

            if len(window) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "تجاوز الحد المسموح — حاول مرة أخرى بعد دقيقة"},
                )
            _rate_store[key].append(now)

            # Periodic cleanup of stale keys (every ~100 requests)
            if sum(len(v) for v in _rate_store.values()) % 100 == 0:
                stale = [k for k, v in _rate_store.items() if not v or now - max(v) > 120]
                for k in stale:
                    del _rate_store[k]

        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


# ── API Key Authentication Middleware ────────────────────────────
_API_KEY = os.getenv("API_KEY", "").strip()

# Paths that don't require authentication
_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header when API_KEY is set in .env."""

    async def dispatch(self, request: Request, call_next):
        # Skip if no API_KEY configured (dev mode)
        if not _API_KEY:
            return await call_next(request)

        path = request.url.path.rstrip("/")

        # Public paths don't need auth
        if path in _PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        # Only check header — query param removed for security (key visible in logs/URLs)
        key = request.headers.get("X-API-Key", "")
        if key != _API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "مفتاح API غير صالح — يرجى إضافة X-API-Key header"},
            )

        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

# CORS — configurable origin whitelist (default: allow all for dev)
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = (
    ["*"] if _cors_origins_raw == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
_cors_final = _cors_origins if _cors_origins != ["*"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_final,
    allow_origin_regex=r"null|file://.*|http://127\.0\.0\.1:\d+|http://localhost:\d+",
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Learning-Key", "Content-Type", "Authorization"],
)

STATIC_DIR = Path(__file__).parent / "static"


# ── Global validation error handler ──────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []
    for err in errors:
        msg = err.get("msg", "خطأ في المدخلات")
        # Clean pydantic prefix
        msg = msg.replace("Value error, ", "")
        messages.append(msg)
    return JSONResponse(
        status_code=422,
        content={"detail": " | ".join(messages)},
    )


@app.on_event("startup")
async def startup():
    await init_schema_context()
    from dashboard_engine import validate_dashboard_sql, validate_dashboard_schema
    validate_dashboard_sql()
    # Validate dashboard SQLs against live DB (catches column/table renames)
    try:
        await validate_dashboard_schema()
    except Exception as e:
        log.warning(f"[STARTUP] Dashboard schema validation skipped: {e}")
    # Initialize Learning Engine
    try:
        from learning.engine import init_learning_engine
        await init_learning_engine()
    except Exception as e:
        log.warning(f"[STARTUP] Learning engine init skipped: {e}")
    # Phase 8: Restore persisted chat sessions from database
    try:
        from memory import load_sessions_from_db
        restored = load_sessions_from_db()
        log.info(f"[STARTUP] Memory persistence: restored {restored} sessions")
    except Exception as e:
        log.warning(f"[STARTUP] Session restore skipped: {e}")
    # Start Proactive Monitoring Engine
    try:
        from proactive.monitor import start_monitor
        start_monitor(interval=900)
        log.info("[STARTUP] Proactive monitoring engine started (interval=900s)")
    except Exception as e:
        log.warning(f"[STARTUP] Proactive monitor start skipped: {e}")
    # Start scheduled cleanup task (Phase 4: production operations)
    asyncio.create_task(_scheduled_cleanup())


async def _scheduled_cleanup():
    """Background task: periodic cleanup of stale learning data."""
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL_HOURS", "6")) * 3600
    log.info(f"[CLEANUP] Scheduled cleanup task started (interval={CLEANUP_INTERVAL}s)")
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            from learning.events import cleanup_old_events
            from learning.metrics import cleanup_old_metrics
            from learning.conversation_bi import cleanup_expired as cleanup_bi_expired
            ev = cleanup_old_events(days=30)
            mt = cleanup_old_metrics(days=7)
            bi = cleanup_bi_expired()
            # Also clean up expired cache entries
            cleanup_all_expired()
            log.info(f"[CLEANUP] Completed: events={ev}, metrics={mt}, bi_contexts={bi}")
        except Exception as e:
            log.warning(f"[CLEANUP] Scheduled cleanup failed: {e}")


app.include_router(chat.router)
app.include_router(stream_router.router)
app.include_router(widget.router)
app.include_router(upload.router)
app.include_router(learning_router.router)
app.include_router(proactive_router.router)
app.include_router(actions_router.router)
app.include_router(exports_router.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health():
    from memory import get_session_stats
    from llm_client import get_usage, _get_provider
    from sql_safety import get_audit_stats

    # DB connectivity check
    db_ok = False
    try:
        from db import get_pool
        pool = await get_pool()
        with pool.acquire() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM DUAL")
        db_ok = True
    except Exception:
        pass

    uptime_seconds = int(time.time() - _startup_time)

    return {
        "status": "ok" if db_ok else "degraded",
        "uptime_seconds": uptime_seconds,
        "database": "connected" if db_ok else "disconnected",
        "llm_provider": _get_provider(),
        "llm_requests": get_usage().get("request_count", 0),
        "memory": get_session_stats(),
        "audit": get_audit_stats(),
        "cache": get_cache_stats(),
    }


@app.get("/observability/traces")
async def get_traces(limit: int = 50):
    """Recent request traces for monitoring."""
    from observability import get_recent_traces, get_performance_summary
    return {
        "traces": get_recent_traces(limit),
        "summary": get_performance_summary(),
    }


@app.get("/observability/errors")
async def get_errors(limit: int = 20):
    """Recent error traces."""
    from observability import get_error_traces
    return {"errors": get_error_traces(limit)}


@app.get("/")
def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
