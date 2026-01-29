# core/users/service.py

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.users.models import User


class UserService:
    """
    UserService для async SQLAlchemy.

    Рекомендуемый паттерн использования в коде:
        async with async_session() as session:
            service = UserService(session)
            user = await service.get_or_create_by_tg_id(...)
            await session.commit()
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logging.getLogger(__name__)

    # -------------------------
    # Base getters
    # -------------------------
    async def get_by_id(self, user_id: int) -> Optional[User]:
        res = await self.session.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        res = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        is_vip: Optional[bool] = None,
    ) -> List[User]:
        query = select(User).limit(limit).offset(offset)
        if status is not None:
            query = query.where(User.status == status)
        if is_vip is not None:
            query = query.where(User.is_vip.is_(is_vip))
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def get_vip_users(self) -> List[User]:
        res = await self.session.execute(
            select(User).where(User.is_vip.is_(True))
        )
        return list(res.scalars().all())

    # -------------------------
    # Create / upsert
    # -------------------------
    async def create(
        self,
        tg_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        status: str = "new",
        source: str = "bot",
    ) -> User:
        user = User(
            tg_id=tg_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            phone=phone,
            email=email,
            status=status,
            source=source,
        )
        self.session.add(user)
        # flush нужен, чтобы получить user.id до commit
        await self.session.flush()
        return user

    async def get_or_create_by_tg_id(
        self,
        tg_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        source: str = "bot",
        update_if_exists: bool = True,
    ) -> User:
        """
        Главный метод для бота.
        - ищем пользователя по tg_id
        - если нет — создаём
        - если есть — (опционально) обновляем имя/username/source
        """
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return await self.create(
                tg_id=tg_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                phone=phone,
                email=email,
                status="new",
                source=source,
            )

        if update_if_exists:
            changed = False
            if first_name is not None and first_name != user.first_name:
                user.first_name = first_name
                changed = True
            if last_name is not None and last_name != user.last_name:
                user.last_name = last_name
                changed = True
            if username is not None and username != user.username:
                user.username = username
                changed = True
            if phone is not None and phone != user.phone:
                user.phone = phone
                changed = True
            if email is not None and email != user.email:
                user.email = email
                changed = True
            # source обычно не хотим перетирать чем-то странным, но если пустой — заполним
            if (user.source is None or user.source == "") and source:
                user.source = source
                changed = True

            if changed:
                # updated_at выставит триггер в БД при UPDATE
                await self.session.flush()

        return user

    async def get_or_create(self, data) -> User:
        return await self.get_or_create_by_tg_id(
            tg_id=data.tg_id,
            first_name=data.first_name,
            last_name=data.last_name,
            username=data.username,
            phone=data.phone,
            email=data.email,
            source=data.source,
        )

    async def update(self, tg_id: int, data) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        await self.session.flush()
        return user

    async def log_event(
        self,
        user_tg_id: int,
        event_type: str,
        event_data: dict,
        description: Optional[str] = None,
    ) -> None:
        self.logger.info(
            "User event: tg_id=%s type=%s description=%s data=%s",
            user_tg_id,
            event_type,
            description,
            event_data,
        )

    # -------------------------
    # Updates (profile / contacts)
    # -------------------------
    async def update_contacts(
        self,
        tg_id: int,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None

        if phone is not None:
            user.phone = phone
        if email is not None:
            user.email = email

        await self.session.flush()
        return user

    async def set_status(self, tg_id: int, status: str) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None
        user.status = status
        await self.session.flush()
        return user

    async def set_source(self, tg_id: int, source: str) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None
        user.source = source
        await self.session.flush()
        return user

    async def set_interests(
        self,
        tg_id: int,
        interested_event_id: Optional[int] = None,
        interested_consultation_id: Optional[int] = None,
    ) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None

        # Можно ставить по одному — если параметр None, не трогаем
        if interested_event_id is not None:
            user.interested_event_id = interested_event_id
        if interested_consultation_id is not None:
            user.interested_consultation_id = interested_consultation_id

        await self.session.flush()
        return user

    # -------------------------
    # VIP helpers
    # -------------------------
    async def set_vip(
        self,
        tg_id: int,
        is_vip: bool = True,
        vip_until: Optional[datetime] = None,
    ) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None

        user.is_vip = is_vip
        user.vip_until = vip_until
        # если ставим VIP — часто логично сменить статус
        if is_vip and user.status != "vip":
            user.status = "vip"

        await self.session.flush()
        return user

    async def make_vip(self, tg_id: int, days: int = 30) -> Optional[User]:
        vip_until = datetime.utcnow() + timedelta(days=days)
        return await self.set_vip(tg_id=tg_id, is_vip=True, vip_until=vip_until)

    async def revoke_vip(self, tg_id: int) -> Optional[User]:
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return None

        user.is_vip = False
        user.vip_until = None
        # статус не трогаем, чтобы не ломать логику CRM (если нужно — меняй тут)
        await self.session.flush()
        return user

    # -------------------------
    # Convenience: commit wrappers
    # -------------------------
    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
