import asyncio
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.db import Base
from core.db import database as db
from core.auth.models import AdminUser
from core.crm.api import router as crm_router
from core.crm.models import (
    CRMUserActivity,
    ChannelInvite,
    GetCourseWebhookEvent,
    IntegrationState,
    UserSubscription,
)
from core.auth.api import router as auth_router
from core.api.ai import router as ai_router
from core.api.analytics import router as analytics_router
from core.api.consultations import router as consultations_router
from core.api.events import router as events_router
from core.api.payments import router as payments_router
from core.api.users import router as users_router
from core.api.webhooks import router as webhooks_router
from core.events.models import Event
from core.payments.models import Payment
from core.catalog.models import CatalogItem

load_dotenv()

logger = logging.getLogger("core.main")

_LOG_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(authorization[=:]\s*)([^\s,;]+)", flags=re.IGNORECASE), r"\1***"),
    (re.compile(r"(bearer\s+)([A-Za-z0-9._\-]+)", flags=re.IGNORECASE), r"\1***"),
    (re.compile(r"(api[_-]?key[=:]\s*)([^\s,;]+)", flags=re.IGNORECASE), r"\1***"),
    (re.compile(r"(token[=:]\s*)([^\s,;]+)", flags=re.IGNORECASE), r"\1***"),
    (re.compile(r"(password[=:]\s*)([^\s,;]+)", flags=re.IGNORECASE), r"\1***"),
    (re.compile(r"(database_url[=:]\s*)([^\s,;]+)", flags=re.IGNORECASE), r"\1***"),
)


def _sanitize_log_message(message: str) -> str:
    safe = str(message or "")
    for pattern, replacement in _LOG_SECRET_PATTERNS:
        safe = pattern.sub(replacement, safe)
    return safe


def _is_db_exception(exc: Exception) -> bool:
    if isinstance(exc, SQLAlchemyError):
        return True
    cls = exc.__class__
    module_name = str(getattr(cls, "__module__", "")).lower()
    class_name = str(getattr(cls, "__name__", "")).lower()
    if "sqlalchemy" in module_name or "asyncpg" in module_name or "psycopg" in module_name:
        return True
    markers = (
        "database",
        "dbapi",
        "operationalerror",
        "interfaceerror",
        "connectionerror",
        "pooltimeout",
        "timeouterror",
    )
    return any(marker in class_name for marker in markers)


def _db_error_short_message(exc: Exception) -> str:
    text_value = str(exc or "").strip().lower()
    if "timeout" in text_value:
        return "timeout"
    if "pool" in text_value:
        return "pool_timeout"
    if "connection" in text_value or "connect" in text_value or "closed" in text_value:
        return "connection_error"
    return "db_error"


def _readyz_db_timeout_seconds() -> float:
    raw = str(os.getenv("READYZ_DB_TIMEOUT_SEC") or "").strip()
    try:
        value = float(raw) if raw else 2.0
    except Exception:
        value = 2.0
    return max(0.5, min(value, 15.0))


def _configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            safe_message = _sanitize_log_message(record.getMessage())
            payload = {
                "ts": datetime.now(tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "service": "web",
                "event": getattr(record, "event", record.name),
                "message": safe_message,
            }
            request_id = getattr(record, "request_id", None)
            if request_id:
                payload["request_id"] = request_id
            path = getattr(record, "path", None)
            if path:
                payload["path"] = path
            method = getattr(record, "method", None)
            if method:
                payload["method"] = method
            status_code = getattr(record, "status_code", None)
            if status_code is not None:
                payload["status_code"] = status_code
            duration_ms = getattr(record, "duration_ms", None)
            if duration_ms is not None:
                payload["duration_ms"] = duration_ms
            error_type = getattr(record, "error_type", None)
            if error_type:
                payload["error_type"] = str(error_type)
            short_message = getattr(record, "short_message", None)
            if short_message:
                payload["short_message"] = _sanitize_log_message(str(short_message))
            return json.dumps(payload, ensure_ascii=False)

    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(JsonFormatter())
            handler.setLevel(level)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.setLevel(level)
        root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = datetime.now(tz=timezone.utc)
    logger.info("startup", extra={"event": "startup"})
    try:
        db.init_db()
        if db.engine is not None:
            async with db.engine.begin() as conn:
                await conn.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        CRMUserActivity.__table__,
                        GetCourseWebhookEvent.__table__,
                        IntegrationState.__table__,
                        UserSubscription.__table__,
                        ChannelInvite.__table__,
                        AdminUser.__table__,
                        Payment.__table__,
                        Event.__table__,
                        CatalogItem.__table__,
                    ],
                )
    except Exception:
        logger.exception("startup_failed", extra={"event": "startup_failed"})
    yield
    logger.info("shutdown", extra={"event": "shutdown"})


environment = (os.getenv("ENVIRONMENT") or "development").strip().lower()
is_production = environment == "production"

app = FastAPI(
    title="Renata Promotion API",
    description="API for events, consultations and payments",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if _is_db_exception(exc):
            logger.warning(
                "db_request_error",
                extra={
                    "event": "db_request_error",
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "error_type": exc.__class__.__name__,
                    "short_message": _db_error_short_message(exc),
                },
            )
        else:
            logger.exception(
                "request_failed",
                extra={
                    "event": "request",
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request",
        extra={
            "event": "request",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(events_router, prefix="/api/events", tags=["Events"])
app.include_router(consultations_router, prefix="/api/consultations", tags=["Consultations"])
app.include_router(payments_router, prefix="/api/payments", tags=["Payments"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(crm_router, prefix="/api/crm", tags=["CRM"])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/healthz")
async def healthz():
    uptime_seconds = 0
    started = getattr(app.state, "started_at", None)
    if started is not None:
        uptime_seconds = int((datetime.now(tz=timezone.utc) - started).total_seconds())
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptimeSeconds": uptime_seconds,
    }


@app.get("/readyz")
async def readyz():
    try:
        if db.async_session is None:
            db.init_db()
        if db.async_session is None:
            raise RuntimeError("Database session is not initialized")
        async with db.async_session() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=_readyz_db_timeout_seconds(),
            )
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/")
async def root():
    return {
        "message": "Renata Promotion API",
        "version": "1.0.0",
        "docs": None if is_production else "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "core.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
