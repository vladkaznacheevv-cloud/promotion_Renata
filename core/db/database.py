import os
import ssl
from urllib.parse import quote_plus, parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from core.db import Base  # <-- ЕДИНСТВЕННЫЙ Base

engine: AsyncEngine | None = None
async_session: sessionmaker | None = None


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else int(default)
    except Exception:
        value = int(default)
    if value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _strip_sslmode(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url

    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "sslmode"]
    if not query:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return _strip_sslmode(url)

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        raise RuntimeError("Database is not configured. Set DATABASE_URL or DB_* env vars.")

    encoded_password = quote_plus(DB_PASSWORD)
    return f"postgresql+asyncpg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def init_db() -> None:
    global engine, async_session
    if engine is not None and async_session is not None:
        return

    database_url = _build_database_url()

    statement_timeout_ms = _int_env("DB_STATEMENT_TIMEOUT_MS", 7000, minimum=1000, maximum=60000)
    connect_timeout_sec = _int_env("DB_CONNECT_TIMEOUT_SEC", 5, minimum=1, maximum=30)
    connect_args = {
        "timeout": connect_timeout_sec,
        "server_settings": {
            "statement_timeout": str(statement_timeout_ms),
        },
    }
    if (os.getenv("DB_SSLMODE") or "").lower() == "require":
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context

    pool_size = _int_env("DB_POOL_SIZE", 5, minimum=1, maximum=50)
    max_overflow = _int_env("DB_MAX_OVERFLOW", 10, minimum=0, maximum=100)
    pool_timeout = _int_env("DB_POOL_TIMEOUT_SEC", 5, minimum=1, maximum=60)

    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    if async_session is None:
        init_db()

    assert async_session is not None
    async with async_session() as session:
        yield session
