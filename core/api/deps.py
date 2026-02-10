from typing import AsyncGenerator
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import database as db

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения сессии БД"""
    if db.async_session is None:
        try:
            db.init_db()
        except Exception:
            raise HTTPException(status_code=503, detail="Database is not available")
    if db.async_session is None:
        raise HTTPException(status_code=503, detail="Database is not available")

    async with db.async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(tg_id: int):
    """Получить текущего пользователя (заглушка для авторизации)"""
    # Здесь можно добавить JWT или Telegram Web App auth
    return tg_id
