# core/events/service.py

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.events.models import Event, UserEvent


class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------
    # Events
    # -------------------------
    async def get_by_id(self, event_id: int) -> Optional[Event]:
        res = await self.session.execute(select(Event).where(Event.id == event_id))
        return res.scalar_one_or_none()

    async def list_active(self, limit: int = 50) -> List[Event]:
        res = await self.session.execute(
            select(Event)
            .where(Event.is_active.is_(True))
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def get_active(self, limit: int = 50) -> List[Event]:
        return await self.list_active(limit=limit)

    async def get_upcoming(self, limit: int = 50) -> List[Event]:
        now = datetime.utcnow()
        res = await self.session.execute(
            select(Event)
            .where(Event.is_active.is_(True))
            .where(Event.starts_at.is_not(None))
            .where(Event.starts_at >= now)
            .order_by(Event.starts_at.asc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        starts_at: Optional[datetime] = None,
        ends_at: Optional[datetime] = None,
        location: Optional[str] = None,
        link_getcourse: Optional[str] = None,
        price: Optional[float] = None,
        capacity: Optional[int] = None,
        is_active: bool = True,
    ) -> Event:
        event = Event(
            title=title,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            location=location,
            link_getcourse=link_getcourse,
            price=price,
            capacity=capacity,
            is_active=is_active,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def set_active(self, event_id: int, is_active: bool) -> Optional[Event]:
        event = await self.get_by_id(event_id)
        if not event:
            return None
        event.is_active = is_active
        await self.session.flush()
        return event

    async def update(self, event_id: int, data) -> Optional[Event]:
        event = await self.get_by_id(event_id)
        if not event:
            return None

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        for key, value in payload.items():
            if hasattr(event, key):
                setattr(event, key, value)
        await self.session.flush()
        return event

    # -------------------------
    # UserEvent (link)
    # -------------------------
    async def register_user(
        self,
        user_id: int,
        event_id: int,
        status: str = "registered",
    ) -> UserEvent:
        """
        Р РµРіРёСЃС‚СЂРёСЂСѓРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РЅР° СЃРѕР±С‹С‚РёРµ.
        Р•СЃР»Рё СѓР¶Рµ РµСЃС‚СЊ Р·Р°РїРёСЃСЊ вЂ” РїСЂРѕСЃС‚Рѕ РѕР±РЅРѕРІРёС‚ status.
        """
        res = await self.session.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user_id, UserEvent.event_id == event_id)
            )
        )
        link = res.scalar_one_or_none()
        if link:
            link.status = status
            await self.session.flush()
            return link

        link = UserEvent(user_id=user_id, event_id=event_id, status=status)
        self.session.add(link)
        await self.session.flush()
        return link

    async def unregister_user(self, user_id: int, event_id: int) -> bool:
        """
        РњСЏРіРєР°СЏ РѕС‚РјРµРЅР°: СЃС‚Р°РІРёРј СЃС‚Р°С‚СѓСЃ cancelled (Р° РЅРµ СѓРґР°Р»СЏРµРј СЃС‚СЂРѕРєСѓ).
        """
        res = await self.session.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user_id, UserEvent.event_id == event_id)
            )
        )
        link = res.scalar_one_or_none()
        if not link:
            return False

        link.status = "cancelled"
        await self.session.flush()
        return True

    async def list_user_events(self, user_id: int, limit: int = 50) -> List[UserEvent]:
        res = await self.session.execute(
            select(UserEvent)
            .where(UserEvent.user_id == user_id)
            .order_by(UserEvent.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def get_user_event(self, user_id: int, event_id: int) -> Optional[UserEvent]:
        res = await self.session.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user_id, UserEvent.event_id == event_id)
            )
        )
        return res.scalar_one_or_none()

    async def is_user_registered(self, user_id: int, event_id: int) -> bool:
        link = await self.get_user_event(user_id, event_id)
        return bool(link and link.status != "cancelled")

    # -------------------------
    # Convenience
    # -------------------------
    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()



