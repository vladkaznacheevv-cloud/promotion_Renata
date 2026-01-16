import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

try:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")
    
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
        
        sync_engine = create_engine(DATABASE_URL.replace("+asyncpg", ""))
        SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
    else:
        # Заглушки для тестов и CI/CD
        engine = None
        async_session = None
        SessionLocal = None
        get_db = lambda: iter([None])
        
except Exception as e:
    # Для случаев когда нет зависимостей или ошибок
    print(f"⚠️ Database not configured: {e}")
    engine = None
    async_session = None
    SessionLocal = None
    get_db = lambda: iter([None])