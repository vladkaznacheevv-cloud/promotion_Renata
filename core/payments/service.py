import logging
import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.payments.models import Payment
from core.payments.schemas import PaymentCreate

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, data: PaymentCreate) -> Payment:
        """Создать платёж"""
        payment = Payment(**data.model_dump())
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        logger.info(f"Платёж создан: id={payment.id}, user_id={data.user_id}")
        return payment
    
    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_yookassa_id(self, yookassa_id: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.payment_id == yookassa_id)
        )
        return result.scalar_one_or_none()
    
    async def mark_as_paid(self, payment_id: int, yookassa_id: str = None) -> Optional[Payment]:
        """Отметить как оплаченный"""
        payment = await self.get_by_id(payment_id)
        if payment:
            payment.status = Payment.STATUS_PAID
            if yookassa_id:
                payment.payment_id = yookassa_id
            await self.session.commit()
            logger.info(f"Платёж оплачен: id={payment_id}")
            return payment
        return None
    
    async def mark_as_cancelled(self, payment_id: int) -> Optional[Payment]:
        """Отметить как отменённый"""
        payment = await self.get_by_id(payment_id)
        if payment:
            payment.status = Payment.STATUS_CANCELLED
            await self.session.commit()
            logger.info(f"Платёж отменён: id={payment_id}")
            return payment
        return None
    
    async def get_user_payments(self, user_id: int) -> List[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_total_revenue(self) -> int:
        """Общая сумма оплат"""
        result = await self.session.execute(
            select(Payment).where(Payment.status == Payment.STATUS_PAID)
        )
        payments = result.scalars().all()
        return sum(p.amount for p in payments)