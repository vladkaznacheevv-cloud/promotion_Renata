from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import async_session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения сессии БД"""
    async with async_session() as session:
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