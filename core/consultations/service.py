from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.consultations.models import Consultation, UserConsultation


class ConsultationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------
    # Consultations
    # -------------------------
    async def get_by_id(self, consultation_id: int) -> Optional[Consultation]:
        res = await self.session.execute(select(Consultation).where(Consultation.id == consultation_id))
        return res.scalar_one_or_none()

    async def list_active(self, limit: int = 50) -> List[Consultation]:
        res = await self.session.execute(
            select(Consultation)
            .where(Consultation.is_active.is_(True))
            .order_by(Consultation.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def get_active(self, limit: int = 50) -> List[Consultation]:
        return await self.list_active(limit=limit)

    async def create(
        self,
        type: str,
        title: str,
        description: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        price: Optional[float] = None,
        available_slots: Optional[int] = None,
        is_active: bool = True,
    ) -> Consultation:
        c = Consultation(
            type=type,
            title=title,
            description=description,
            duration_minutes=duration_minutes,
            price=price,
            available_slots=available_slots,
            is_active=is_active,
        )
        self.session.add(c)
        await self.session.flush()
        return c

    async def set_active(self, consultation_id: int, is_active: bool) -> Optional[Consultation]:
        c = await self.get_by_id(consultation_id)
        if not c:
            return None
        c.is_active = is_active
        await self.session.flush()
        return c

    # -------------------------
    # UserConsultation (booking)
    # -------------------------
    async def book(
        self,
        user_id: int,
        consultation_id: int,
        scheduled_at: Optional[datetime] = None,
        status: str = "scheduled",
        zoom_link: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> UserConsultation:
        """
        Создаёт запись на консультацию.
        По умолчанию scheduled_at может быть None, если сначала "заявка", а время назначат позже.
        """
        uc = UserConsultation(
            user_id=user_id,
            consultation_id=consultation_id,
            scheduled_at=scheduled_at,
            status=status,
            zoom_link=zoom_link,
            notes=notes,
        )
        self.session.add(uc)
        await self.session.flush()
        return uc

    async def set_status(self, user_consultation_id: int, status: str) -> Optional[UserConsultation]:
        res = await self.session.execute(
            select(UserConsultation).where(UserConsultation.id == user_consultation_id)
        )
        uc = res.scalar_one_or_none()
        if not uc:
            return None
        uc.status = status
        await self.session.flush()
        return uc

    async def reschedule(
        self,
        user_consultation_id: int,
        scheduled_at: datetime,
        zoom_link: Optional[str] = None,
    ) -> Optional[UserConsultation]:
        res = await self.session.execute(
            select(UserConsultation).where(UserConsultation.id == user_consultation_id)
        )
        uc = res.scalar_one_or_none()
        if not uc:
            return None

        uc.scheduled_at = scheduled_at
        if zoom_link is not None:
            uc.zoom_link = zoom_link
        await self.session.flush()
        return uc

    async def list_user_bookings(self, user_id: int, limit: int = 50) -> List[UserConsultation]:
        res = await self.session.execute(
            select(UserConsultation)
            .where(UserConsultation.user_id == user_id)
            .order_by(UserConsultation.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    # -------------------------
    # Convenience
    # -------------------------
    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
