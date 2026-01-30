# core/payments/service.py

from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.payments.models import Payment

class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        res = await self.session.execute(select(Payment).where(Payment.id == payment_id))
        return res.scalar_one_or_none()

    async def list_by_user(self, user_id: int, limit: int = 50) -> List[Payment]:
        res = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def get_user_payments(self, user_id: int, limit: int = 50) -> List[Payment]:
        return await self.list_by_user(user_id=user_id, limit=limit)

    async def create_pending(
        self,
        user_id: int,
        amount: int,
        provider: Optional[str] = None,
        external_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Payment:
        p = Payment(
            user_id=user_id,
            amount=amount,
            status="pending",
            provider=provider,
            external_id=external_id,
            metadata_=metadata,
        )
        self.session.add(p)
        await self.session.flush()
        return p

    async def create(self, data) -> Payment:
        payload = data.model_dump() if hasattr(data, "model_dump") else dict(data)
        return await self.create_pending(
            user_id=payload.get("user_id"),
            amount=payload.get("amount"),
            provider=payload.get("provider"),
            external_id=payload.get("external_id"),
            metadata=payload.get("metadata"),
        )

    async def set_status(
        self,
        payment_id: int,
        status: str,
        external_id: Optional[str] = None,
        provider: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Payment]:
        p = await self.get_by_id(payment_id)
        if not p:
            return None

        p.status = status
        if external_id is not None:
            p.external_id = external_id
        if provider is not None:
            p.provider = provider
        if metadata is not None:
            # перезапишем или можно сделать merge — если нужно, скажи
            p.metadata_ = metadata

        await self.session.flush()
        return p

    async def mark_paid(
        self,
        payment_id: int,
        external_id: Optional[str] = None,
        provider: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Payment]:
        return await self.set_status(
            payment_id=payment_id,
            status="paid",
            external_id=external_id,
            provider=provider,
            metadata=metadata,
        )

    async def mark_as_paid(self, payment_id: int, external_id: Optional[str] = None) -> Optional[Payment]:
        return await self.mark_paid(payment_id=payment_id, external_id=external_id)

    async def mark_failed(
        self,
        payment_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Payment]:
        return await self.set_status(payment_id=payment_id, status="failed", metadata=metadata)

    async def get_total_revenue(self) -> int:
        res = await self.session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid")
        )
        return int(res.scalar() or 0)

    # -------------------------
    # Convenience
    # -------------------------
    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
