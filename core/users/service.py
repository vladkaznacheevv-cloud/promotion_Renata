import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.logging import logger
from core.users.models import User
from core.users.schemas import UserCreate, UserUpdate

class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create(self, data: UserCreate) -> User:
        """Найти или создать пользователя"""
        result = await self.session.execute(
            select(User).where(User.tg_id == data.tg_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем данные
            if data.first_name: user.first_name = data.first_name
            if data.last_name: user.last_name = data.last_name
            if data.username: user.username = data.username
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Пользователь обновлён: tg_id={data.tg_id}")
            return user
        
        # Создаём нового
        user = User(**data.model_dump())
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        logger.info(f"Пользователь создан: tg_id={data.tg_id}")
        return user
    
    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Получить пользователя по TG ID"""
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Получить всех пользователей с пагинацией"""
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return result.scalars().all()
    
    async def update(self, tg_id: int, data: UserUpdate) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user:
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(user, key, value)
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Пользователь обновлён: tg_id={tg_id}")
            return user
        return None
    
    async def make_vip(self, tg_id: int, days: int = 30) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user:
            user.is_vip = True
            user.vip_until = datetime.utcnow() + datetime.timedelta(days=days)
            user.status = User.STATUS_VIP
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Пользователь стал VIP: tg_id={tg_id}")
            return user
        return None
    
    async def get_vip_users(self) -> List[User]:
        result = await self.session.execute(
            select(User).where(User.is_vip == True).order_by(User.vip_until)
        )
        return result.scalars().all()