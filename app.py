import os
import sys
import io
import time
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from routers import chat, widget, upload
from schema_loader import init_schema_context
from cache import get_all_stats as get_cache_stats, invalidate_all as invalidate_cache, cleanup_all_expired

load_dotenv()

log = logging.getLogger("app")

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="JustClick AI Chatbot", version="1.0")

_startup_time = time.time()


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

        # Check header or query param
        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if key != _API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "مفتاح API غير صالح — يرجى إضافة X-API-Key header"},
            )

        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

# CORS — allow APEX and any domain to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


app.include_router(chat.router)
app.include_router(widget.router)
app.include_router(upload.router)

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


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
