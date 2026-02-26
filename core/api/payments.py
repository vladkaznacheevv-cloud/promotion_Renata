from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.api.deps import get_db
from core.api.webhooks import process_game10_payment_success
from core.crm.models import YooKassaPayment
from core.payments.models import Payment
from core.payments.schemas import PaymentCreate, PaymentResponse
from core.payments.service import PaymentService
from core.users.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

GAME10_PRICE_RUB = 5000
GAME10_PRODUCT = "game10"


class Game10PaymentCreateIn(BaseModel):
    tg_id: int = Field(..., ge=1)


class Game10PaymentCreateOut(BaseModel):
    payment_id: str
    confirmation_url: str
    amount_rub: int
    is_reused: bool | None = None
    reuse_reason: str | None = None


class YooKassaStatusCheckIn(BaseModel):
    payment_id: str = Field(..., min_length=1, max_length=128)
    tg_id: int | None = Field(default=None, ge=1)


class YooKassaStatusCheckOut(BaseModel):
    ok: bool = True
    payment_id: str
    status: str
    updated: bool = False
    processed_success: bool = False
    already_in_channel: bool | None = None
    result: str | None = None


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
    bot_return = (os.getenv("TELEGRAM_BOT_RETURN_URL") or "").strip()
    if bot_return:
        if not bot_return.lower().startswith(("http://", "https://")):
            bot_return = f"https://{bot_return}"
        return bot_return
    base = _normalized_public_base_url()
    if base:
        return f"{base}/"
    return "https://example.com/"


def _yookassa_notification_url() -> str | None:
    base = _normalized_public_base_url()
    token = (os.getenv("YOOKASSA_WEBHOOK_TOKEN") or "").strip()
    if not base or not token:
        return None
    return f"{base}/api/webhooks/yookassa/{token}"


def _normalized_public_base_url() -> str:
    base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.lower().startswith(("http://", "https://")):
        base = f"https://{base}"
    return base


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except Exception:
        return default


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reuse_ttl_minutes() -> int:
    return max(1, _int_env("YOOKASSA_REUSE_TTL_MINUTES", 15))


def _is_within_reuse_ttl(created_at: datetime | None) -> bool:
    created = _normalize_dt(created_at)
    if created is None:
        return False
    return (_utcnow() - created) <= timedelta(minutes=_reuse_ttl_minutes())


def _normalize_phone_for_receipt(value: str | None) -> str | None:
    if not value:
        return None
    phone = "".join(ch for ch in str(value).strip() if ch.isdigit() or ch == "+")
    return phone or None


def _build_yookassa_receipt(
    *,
    email: str | None,
    phone: str | None,
    amount_rub: int,
    item_description: str | None = None,
) -> dict:
    customer: dict[str, str] = {}
    email_value = (str(email).strip() if email else "") or None
    phone_value = _normalize_phone_for_receipt(phone)
    if email_value:
        customer["email"] = email_value
    if phone_value:
        customer["phone"] = phone_value
    return {
        "customer": customer,
        "tax_system_code": _int_env("YOOKASSA_TAX_SYSTEM_CODE", 2),
        "items": [
            {
                "description": str(item_description or "Игра 10:0 — доступ в закрытое сообщество"),
                "quantity": "1.00",
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "vat_code": _int_env("YOOKASSA_VAT_CODE", 1),
                "payment_subject": "service",
                "payment_mode": "full_payment",
            }
        ],
    }


async def _get_receipt_customer_contact(db: AsyncSession, *, tg_id: int) -> tuple[str | None, str | None]:
    row = await db.execute(
        select(User.email, User.phone)
        .where(User.tg_id == tg_id)
        .limit(1)
    )
    mapping = row.mappings().first()
    if not mapping:
        return None, None
    email = str(mapping.get("email") or "").strip() or None
    phone = str(mapping.get("phone") or "").strip() or None
    return email, phone


async def _create_yookassa_payment(
    *,
    tg_id: int,
    customer_email: str | None,
    customer_phone: str | None,
    amount_rub: int = GAME10_PRICE_RUB,
    product_code: str = GAME10_PRODUCT,
    payment_description: str | None = None,
    receipt_item_description: str | None = None,
) -> dict:
    shop_id = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
    secret_key = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
    if not shop_id or not secret_key:
        raise HTTPException(status_code=503, detail="YOOKASSA credentials not configured")

    idempotence_key = uuid4().hex
    request_body = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": _public_return_url()},
        "description": str(payment_description or "Игра 10:0 (доступ в закрытый канал)"),
        "metadata": {"tg_id": str(tg_id), "product": str(product_code)},
        "receipt": _build_yookassa_receipt(
            email=customer_email,
            phone=customer_phone,
            amount_rub=amount_rub,
            item_description=receipt_item_description,
        ),
    }
    notification_url = _yookassa_notification_url()
    if notification_url:
        request_body["notification_url"] = notification_url
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


async def _get_yookassa_payment_status(payment_id: str) -> str | None:
    payment_id = str(payment_id or "").strip()
    if not payment_id:
        return None
    shop_id = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
    secret_key = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
    if not shop_id or not secret_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                auth=(shop_id, secret_key),
            )
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    return str(payload.get("status") or "").strip().lower() or None


async def _should_reuse_existing_game10_payment(existing: YooKassaPayment | None) -> tuple[bool, str]:
    if existing is None or not existing.payment_id or not existing.confirmation_url:
        return False, "missing_existing"
    if not _is_within_reuse_ttl(existing.created_at):
        return False, "expired_ttl"
    remote_status = await _get_yookassa_payment_status(str(existing.payment_id))
    if remote_status and remote_status not in {"pending", "waiting_for_capture"}:
        return False, "status_not_pending"
    return True, "fresh"


async def _get_last_pending_game10_payment(
    db: AsyncSession,
    *,
    tg_id: int,
    product_code: str,
    amount_rub: int,
) -> YooKassaPayment | None:
    existing_row = await db.execute(
        select(YooKassaPayment)
        .where(YooKassaPayment.tg_id == tg_id)
        .where(YooKassaPayment.product == str(product_code))
        .where(YooKassaPayment.amount_rub == int(amount_rub))
        .where(YooKassaPayment.status.in_(["pending", "waiting_for_capture", "created"]))
        .where(YooKassaPayment.confirmation_url.is_not(None))
        .order_by(YooKassaPayment.id.desc())
        .limit(1)
    )
    return existing_row.scalar_one_or_none()


async def _create_game10_payment_common(
    *,
    request: Request,
    body: Optional[Game10PaymentCreateIn],
    tg_id: Optional[int],
    db: AsyncSession,
    product_code: str,
    amount_rub: int,
    payment_description: str,
    receipt_item_description: str,
) -> Game10PaymentCreateOut:
    _require_bot_api_token(request)
    target_tg_id = int(tg_id or (body.tg_id if body is not None else 0))
    if target_tg_id <= 0:
        raise HTTPException(status_code=422, detail="tg_id is required")

    existing = await _get_last_pending_game10_payment(
        db,
        tg_id=target_tg_id,
        product_code=product_code,
        amount_rub=amount_rub,
    )
    can_reuse, reuse_reason = await _should_reuse_existing_game10_payment(existing)
    if can_reuse and existing and existing.payment_id and existing.confirmation_url:
        return Game10PaymentCreateOut(
            payment_id=str(existing.payment_id),
            confirmation_url=str(existing.confirmation_url),
            amount_rub=int(existing.amount_rub or amount_rub),
            is_reused=True,
            reuse_reason=reuse_reason,
        )

    email, phone = await _get_receipt_customer_contact(db, tg_id=target_tg_id)
    logger.info(
        "Game10 YooKassa receipt contacts: tg_id=%s has_email=%s has_phone=%s amount_rub=%s product=%s",
        target_tg_id,
        bool(email),
        bool(phone),
        amount_rub,
        product_code,
    )
    if not email and not phone:
        raise HTTPException(
            status_code=400,
            detail="Для оплаты нужен телефон или email (для отправки чека). Запросите контакты у клиента.",
        )

    created = await _create_yookassa_payment(
        tg_id=target_tg_id,
        customer_email=email,
        customer_phone=phone,
        amount_rub=amount_rub,
        product_code=product_code,
        payment_description=payment_description,
        receipt_item_description=receipt_item_description,
    )
    logger.info(
        "Game10 YooKassa payment created: tg_id=%s payment_id=%s status=%s has_email=%s has_phone=%s amount_rub=%s product=%s notification_url_present=%s",
        target_tg_id,
        created.get("payment_id"),
        created.get("status"),
        bool(email),
        bool(phone),
        amount_rub,
        product_code,
        bool(_yookassa_notification_url()),
    )
    record = YooKassaPayment(
        tg_id=target_tg_id,
        product=product_code,
        amount_rub=amount_rub,
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
        amount_rub=amount_rub,
        is_reused=False,
        reuse_reason=("new" if reuse_reason in {"missing_existing", "fresh"} else reuse_reason),
    )


@router.post("/game10/create", response_model=Game10PaymentCreateOut)
async def create_game10_payment(
    request: Request,
    body: Optional[Game10PaymentCreateIn] = Body(default=None),
    tg_id: Optional[int] = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await _create_game10_payment_common(
        request=request,
        body=body,
        tg_id=tg_id,
        db=db,
        product_code=GAME10_PRODUCT,
        amount_rub=GAME10_PRICE_RUB,
        payment_description="Игра 10:0 (доступ в закрытый канал)",
        receipt_item_description="Игра 10:0 — доступ в закрытое сообщество",
    )



@router.post("/yookassa/status", response_model=YooKassaStatusCheckOut)
async def check_yookassa_payment_status(
    request: Request,
    body: YooKassaStatusCheckIn,
    db: AsyncSession = Depends(get_db),
):
    _require_bot_api_token(request)
    payment_id = str(body.payment_id or "").strip()
    if not payment_id:
        raise HTTPException(status_code=422, detail="payment_id is required")

    row = await db.execute(
        select(YooKassaPayment).where(YooKassaPayment.payment_id == payment_id).limit(1)
    )
    payment = row.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    if body.tg_id is not None and int(payment.tg_id or 0) != int(body.tg_id):
        raise HTTPException(status_code=409, detail="payment_id does not belong to tg_id")

    remote_status = await _get_yookassa_payment_status(payment_id)
    status = str(remote_status or payment.status or "unknown").strip().lower() or "unknown"
    previous_status = str(payment.status or "").strip().lower()
    payment.status = status
    if status == "succeeded" and payment.paid_at is None:
        payment.paid_at = _utcnow()
    await db.flush()
    updated = status != previous_status or (status == "succeeded" and payment.paid_at is not None)

    processed_success = False
    already_in_channel: bool | None = None
    result_label: str | None = None
    if status == "succeeded" and int(payment.tg_id or 0) > 0:
        success_result = await process_game10_payment_success(
            db=db,
            payment_id=payment_id,
            tg_id=int(payment.tg_id),
        )
        processed_success = True
        already_in_channel = bool(success_result.get("already_in_channel"))
        result_label = str(success_result.get("result") or "")
        logger.info(
            "YooKassa status check processed: payment_id=%s tg_id=%s status=%s result=%s",
            payment_id,
            int(payment.tg_id),
            status,
            result_label or "-",
        )
    else:
        logger.info(
            "YooKassa status check: payment_id=%s status=%s",
            payment_id,
            status,
        )

    return YooKassaStatusCheckOut(
        ok=True,
        payment_id=payment_id,
        status=status,
        updated=bool(updated),
        processed_success=processed_success,
        already_in_channel=already_in_channel,
        result=result_label,
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
