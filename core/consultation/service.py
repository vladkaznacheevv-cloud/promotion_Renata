import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.consultations.models import Consultation, UserConsultation
from core.consultations.schemas import ConsultationCreate, ConsultationUpdate

logger = logging.getLogger(__name__)

class ConsultationService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active(self) -> List[Consultation]:
        result = await self.session.execute(
            select(Consultation).where(Consultation.is_active == True)
        )
        return result.scalars().all()
    
    async def get_by_id(self, consultation_id: int) -> Optional[Consultation]:
        result = await self.session.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, data: ConsultationCreate) -> Consultation:
        consultation = Consultation(**data.model_dump())
        self.session.add(consultation)
        await self.session.commit()
        await self.session.refresh(consultation)
        logger.info(f"Консультация создана: id={consultation.id}")
        return consultation
    
    async def schedule(self, user_id: int, consultation_id: int, scheduled_at) -> UserConsultation:
        """Записать пользователя на консультацию"""
        record = UserConsultation(
            user_id=user_id,
            consultation_id=consultation_id,
            scheduled_at=scheduled_at,
            status=UserConsultation.STATUS_SCHEDULED
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.info(f"Запись на консультацию: user={user_id}, consultation={consultation_id}")
        return record