import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

try:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    
    if DB_USER and DB_PASSWORD and DB_HOST and DB_PORT and DB_NAME:
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
    else:
        # Заглушки для тестов
        engine = None
        async_session = None
        get_db = lambda: iter([None])
        
except Exception as e:
    print(f"⚠️ Database not configured: {e}")
    engine = None
    async_session = None
    get_db = lambda: iter([None])