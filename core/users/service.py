# core/users/service.py

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
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

    # -------------------------
    # Base getters
    # -------------------------
    async def get_by_id(self, user_id: int) -> Optional[User]:
        res = await self.session.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        res = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()

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
            # source обычно не хотим перетирать чем-то странным, но если пустой — заполним
            if (user.source is None or user.source == "") and source:
                user.source = source
                changed = True

            if changed:
                # updated_at выставит триггер в БД при UPDATE
                await self.session.flush()

        return user

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
