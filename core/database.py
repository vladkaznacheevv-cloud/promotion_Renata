import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

Base = declarative_base()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = None
async_session = None

if all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    encoded_password = quote_plus(DB_PASSWORD)
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    if os.getenv("DB_SSLMODE") == "require":
        DATABASE_URL += "?ssl=require"

    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get_db():
        async with async_session() as session:
            yield session
else:
    async def get_db():
        raise RuntimeError("Database is not configured. Check DB_* env vars.")