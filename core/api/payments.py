from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.api.deps import get_db
from core.payments.models import Payment
from core.payments.schemas import PaymentCreate, PaymentResponse
from core.payments.service import PaymentService

router = APIRouter()


@router.get("/", response_model=List[PaymentResponse])
async def get_payments(
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить платежи"""
    service = PaymentService(db)
    
    if user_id:
        return await service.get_user_payments(user_id)
    
    # Для админки - все платежи
    result = await db.execute(
        select(Payment).order_by(Payment.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    """Получить платёж по ID"""
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    return payment


@router.post("/", response_model=PaymentResponse)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать платёж"""
    service = PaymentService(db)
    return await service.create(data)


@router.post("/{payment_id}/confirm")
async def confirm_payment(
    payment_id: int,
    yookassa_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Подтвердить оплату (webhook от YooKassa)"""
    service = PaymentService(db)
    payment = await service.mark_as_paid(payment_id, yookassa_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    return {"status": "paid", "payment_id": payment.id}


@router.get("/stats/revenue")
async def get_revenue(db: AsyncSession = Depends(get_db)):
    """Общая статистика выручки"""
    service = PaymentService(db)
    total = await service.get_total_revenue()
    return {"total_revenue_kopecks": total, "total_revenue_rubles": total / 100}