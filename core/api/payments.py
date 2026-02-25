from __future__ import annotations

import os
from uuid import uuid4
from typing import List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.api.deps import get_db
from core.crm.models import YooKassaPayment
from core.payments.models import Payment
from core.payments.schemas import PaymentCreate, PaymentResponse
from core.payments.service import PaymentService

router = APIRouter()

GAME10_PRICE_RUB = 5000


class Game10PaymentCreateIn(BaseModel):
    tg_id: int = Field(..., ge=1)


class Game10PaymentCreateOut(BaseModel):
    payment_id: str
    confirmation_url: str
    amount_rub: int


def _extract_internal_token(request: Request) -> str:
    token = (request.headers.get("X-Bot-Api-Token") or request.headers.get("x-bot-api-token") or "").strip()
    if token:
        return token
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _require_bot_api_token(request: Request) -> None:
    expected = (os.getenv("BOT_API_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="BOT_API_TOKEN not configured")
    incoming = _extract_internal_token(request)
    if incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _public_return_url() -> str:
    base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        return f"{base}/"
    return "https://example.com/"


async def _create_yookassa_payment(*, tg_id: int) -> dict:
    shop_id = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
    secret_key = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
    if not shop_id or not secret_key:
        raise HTTPException(status_code=503, detail="YOOKASSA credentials not configured")

    idempotence_key = uuid4().hex
    request_body = {
        "amount": {"value": f"{GAME10_PRICE_RUB:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": _public_return_url()},
        "description": "Игра 10:0 (доступ в закрытый канал)",
        "metadata": {"tg_id": str(tg_id), "product": "game10"},
    }
    headers = {"Idempotence-Key": idempotence_key}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.yookassa.ru/v3/payments",
                json=request_body,
                headers=headers,
                auth=(shop_id, secret_key),
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YooKassa request failed: {exc.__class__.__name__}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"YooKassa error: HTTP {response.status_code}")

    try:
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="YooKassa invalid JSON response") from exc

    payment_id = str(payload.get("id") or "").strip()
    confirmation_url = str(((payload.get("confirmation") or {}).get("confirmation_url") or "")).strip()
    if not payment_id:
        raise HTTPException(status_code=502, detail="YooKassa response missing payment_id")
    if not confirmation_url:
        raise HTTPException(status_code=502, detail="YooKassa response missing confirmation_url")
    return {
        "payment_id": payment_id,
        "confirmation_url": confirmation_url,
        "status": str(payload.get("status") or "pending"),
        "idempotence_key": idempotence_key,
    }


@router.post("/game10/create", response_model=Game10PaymentCreateOut)
async def create_game10_payment(
    request: Request,
    body: Optional[Game10PaymentCreateIn] = Body(default=None),
    tg_id: Optional[int] = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    _require_bot_api_token(request)
    target_tg_id = int(tg_id or (body.tg_id if body is not None else 0))
    if target_tg_id <= 0:
        raise HTTPException(status_code=422, detail="tg_id is required")

    existing_row = await db.execute(
        select(YooKassaPayment)
        .where(YooKassaPayment.tg_id == target_tg_id)
        .where(YooKassaPayment.product == "game10")
        .where(YooKassaPayment.status == "pending")
        .where(YooKassaPayment.confirmation_url.is_not(None))
        .order_by(YooKassaPayment.id.desc())
        .limit(1)
    )
    existing = existing_row.scalar_one_or_none()
    if existing and existing.payment_id and existing.confirmation_url:
        return Game10PaymentCreateOut(
            payment_id=str(existing.payment_id),
            confirmation_url=str(existing.confirmation_url),
            amount_rub=int(existing.amount_rub or GAME10_PRICE_RUB),
        )

    created = await _create_yookassa_payment(tg_id=target_tg_id)
    record = YooKassaPayment(
        tg_id=target_tg_id,
        product="game10",
        amount_rub=GAME10_PRICE_RUB,
        payment_id=created["payment_id"],
        idempotence_key=created["idempotence_key"],
        status=created["status"] or "pending",
        confirmation_url=created["confirmation_url"],
    )
    db.add(record)
    await db.flush()
    return Game10PaymentCreateOut(
        payment_id=created["payment_id"],
        confirmation_url=created["confirmation_url"],
        amount_rub=GAME10_PRICE_RUB,
    )


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
        payments = await service.get_user_payments(user_id, limit=limit)
        if status:
            payments = [p for p in payments if p.status == status]
        return payments
    
    # Для админки - все платежи
    query = select(Payment).order_by(Payment.created_at.desc()).limit(limit)
    if status:
        query = query.where(Payment.status == status)
    result = await db.execute(query)
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
