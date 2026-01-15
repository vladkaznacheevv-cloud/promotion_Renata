import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")

if not DB_USER or not DB_PASSWORD or not DB_HOST or not DB_PORT or not DB_NAME:
    raise ValueError("❌ Не все переменные БД указаны в .env")

encoded_password = quote_plus(DB_PASSWORD)
DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
if os.getenv("DB_SSLMODE") == "require":
    DATABASE_URL += "?ssl=require"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

# Добавляем для совместимости с тестами
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)