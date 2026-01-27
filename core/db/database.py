# core/database.py
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from core.db import Base

load_dotenv()

Base = declarative_base()

engine: AsyncEngine | None = None
async_session: sessionmaker | None = None

def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        raise RuntimeError("Database is not configured. Set DATABASE_URL or DB_* env vars.")

    encoded_password = quote_plus(DB_PASSWORD)
    url = f"postgresql+asyncpg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    if os.getenv("DB_SSLMODE") == "require" and "?" not in url:
        url += "?ssl=require"

    return url


def init_db() -> None:
    """✅ Вызывается ОДИН РАЗ при старте API/бота. Можно вызывать повторно — будет no-op."""
    global engine, async_session
    if engine is not None and async_session is not None:
        return

    database_url = _build_database_url()
    engine = create_async_engine(database_url, echo=False, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI Depends / сервисы. Сам поднимет engine, если ещё не поднят."""
    if async_session is None:
        init_db()

    assert async_session is not None
    async with async_session() as session:
        yield session
