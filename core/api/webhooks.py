from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.crm.models import YooKassaPayment, YooKassaWebhookEvent
from core.crm.service import CRMService
from core.integrations.getcourse import GetCourseService
from core.payments.models import Payment
from core.users.models import User


router = APIRouter()
logger = logging.getLogger(__name__)


def _get_webhook_token(request: Request) -> str:
    token = (request.headers.get("X-Webhook-Token") or request.headers.get("x-webhook-token") or "").strip()
    if token:
        return token
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


async def _parse_payload(request: Request) -> dict[str, Any]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
        if isinstance(body, dict):
            return body
        return {"payload": body}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload = {k: v for k, v in form.items()}
        if "payload" in payload and isinstance(payload["payload"], str):
            try:
                decoded = json.loads(payload["payload"])
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                pass
        return payload

    raw = (await request.body()).decode("utf-8", errors="replace").strip()
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, dict):
            return decoded
        return {"payload": decoded}
    except Exception:
        return {"raw": raw}


async def _telegram_api_post(method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        return None
    endpoint = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, json=payload)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    result = data.get("result")
    return result if isinstance(result, dict) else {"result": result}


async def _create_game10_join_request_link(*, tg_id: int, payment_id: str) -> str | None:
    channel_id = (os.getenv("TELEGRAM_PRIVATE_CHANNEL_ID") or "").strip()
    if not channel_id:
        return None
    expire_dt = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "chat_id": channel_id,
        "creates_join_request": True,
        "member_limit": 1,
        "expire_date": int(expire_dt.timestamp()),
        "name": f"game10:{tg_id}:{payment_id}"[:32],
    }
    result = await _telegram_api_post("createChatInviteLink", payload)
    if not result:
        payload.pop("member_limit", None)
        result = await _telegram_api_post("createChatInviteLink", payload)
    if not result:
        return None
    invite_link = str(result.get("invite_link") or "").strip()
    return invite_link or None


async def _get_chat_member_status(*, chat_id: str | int, user_id: int) -> str | None:
    result = await _telegram_api_post("getChatMember", {"chat_id": chat_id, "user_id": int(user_id)})
    if not result:
        return None
    status = str(result.get("status") or "").strip().lower()
    return status or None


def _is_active_channel_member_status(status: str | None) -> bool:
    return str(status or "").strip().lower() in {"member", "administrator", "creator"}


async def _send_game10_paid_message(*, tg_id: int, invite_link: str | None) -> None:
    reply_markup = None
    text = "Оплата прошла. Доступ к закрытому каналу открыт."
    if invite_link:
        reply_markup = {
            "inline_keyboard": [[{"text": "Вступить в канал", "url": invite_link}]],
        }
        text = "Оплата подтверждена. Нажмите «Вступить в канал»."
    payload = {
        "chat_id": tg_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    await _telegram_api_post("sendMessage", payload)


async def _send_game10_already_member_message(*, tg_id: int) -> None:
    await _telegram_api_post(
        "sendMessage",
        {
            "chat_id": tg_id,
            "text": "Вы уже состоите в закрытом канале.",
        },
    )


async def _upsert_crm_game10_payment(*, db: AsyncSession, tg_id: int, payment_id: str) -> str:
    """Mirror succeeded YooKassa payment into CRM payments table for revenue screens."""
    payment_id = str(payment_id or "").strip()
    if not payment_id:
        return "no_payment_id"

    yk_row = await db.execute(
        select(YooKassaPayment)
        .where(YooKassaPayment.payment_id == payment_id)
        .limit(1)
    )
    yk_payment = yk_row.scalar_one_or_none()

    user_row = await db.execute(
        select(User).where(User.tg_id == int(tg_id)).limit(1)
    )
    user = user_row.scalar_one_or_none()
    if user is None:
        return "user_not_found"

    amount_rub = int(getattr(yk_payment, "amount_rub", 0) or 5000)
    status = str(getattr(yk_payment, "status", "succeeded") or "succeeded").strip().lower()

    row = await db.execute(
        select(Payment)
        .where(Payment.external_id == payment_id)
        .limit(1)
    )
    crm_payment = row.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if crm_payment is None:
        crm_payment = Payment(
            user_id=int(user.id),
            amount=amount_rub,
            status="paid",
            provider="yookassa",
            external_id=payment_id,
            currency="RUB",
            source="game10",
            paid_at=now,
            updated_at=now,
        )
        db.add(crm_payment)
        await db.flush()
        return "created"

    crm_payment.user_id = int(user.id)
    if amount_rub > 0:
        crm_payment.amount = amount_rub
    crm_payment.provider = crm_payment.provider or "yookassa"
    crm_payment.external_id = payment_id
    crm_payment.currency = crm_payment.currency or "RUB"
    crm_payment.source = crm_payment.source or "game10"
    crm_payment.status = "paid" if status in {"succeeded", "paid"} else (crm_payment.status or "paid")
    crm_payment.updated_at = now
    if crm_payment.paid_at is None:
        crm_payment.paid_at = now
    await db.flush()
    return "updated"


async def process_game10_payment_success(*, db: AsyncSession, payment_id: str, tg_id: int) -> dict[str, Any]:
    service = CRMService(db)
    await service.mark_private_channel_paid(int(tg_id), ensure_invite=False)
    crm_payment_result = await _upsert_crm_game10_payment(db=db, tg_id=int(tg_id), payment_id=str(payment_id))

    channel_id = (os.getenv("TELEGRAM_PRIVATE_CHANNEL_ID") or "").strip()
    member_status = None
    if channel_id:
        member_status = await _get_chat_member_status(chat_id=channel_id, user_id=int(tg_id))
    if _is_active_channel_member_status(member_status):
        await _send_game10_already_member_message(tg_id=int(tg_id))
        return {
            "result": "already_member",
            "already_in_channel": True,
            "invite_sent": False,
            "member_status": member_status or "",
            "crm_payment": crm_payment_result,
        }

    invite_link = await _create_game10_join_request_link(tg_id=int(tg_id), payment_id=str(payment_id))
    await _send_game10_paid_message(tg_id=int(tg_id), invite_link=invite_link)
    return {
        "result": "invite_sent" if invite_link else "paid_notified_no_invite",
        "already_in_channel": False,
        "invite_sent": bool(invite_link),
        "member_status": member_status or "",
        "crm_payment": crm_payment_result,
    }


@router.post("/getcourse")
async def getcourse_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    expected_token = (os.getenv("GETCOURSE_WEBHOOK_TOKEN") or "").strip()
    incoming_token = _get_webhook_token(request)
    if not expected_token or incoming_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await _parse_payload(request)
    integration = GetCourseService(db)
    await integration.store_webhook_event(payload)
    await db.commit()
    return {"ok": True}


@router.post("/yookassa/{token}")
async def yookassa_webhook(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    expected = (os.getenv("YOOKASSA_WEBHOOK_TOKEN") or "").strip()
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await _parse_payload(request)
    event_type = str(payload.get("event") or "").strip() or "unknown"
    obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
    payment_id = str((obj or {}).get("id") or "").strip()
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment_id")

    raw_json = json.dumps(payload, ensure_ascii=False)

    try:
        event_row = YooKassaWebhookEvent(
            event_type=event_type,
            payment_id=payment_id,
            raw_json=raw_json,
        )
        db.add(event_row)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("YooKassa webhook duplicate: event=%s payment_id=%s", event_type, payment_id)
        return {"ok": True, "duplicate": True}

    payment_row = await db.execute(
        select(YooKassaPayment).where(YooKassaPayment.payment_id == payment_id).limit(1)
    )
    payment = payment_row.scalar_one_or_none()

    metadata = obj.get("metadata") if isinstance(obj, dict) else {}
    tg_id_raw = (metadata or {}).get("tg_id")
    product = str((metadata or {}).get("product") or "game10").strip() or "game10"
    tg_id_value: int | None = None
    try:
        if tg_id_raw is not None:
            tg_id_value = int(str(tg_id_raw).strip())
    except Exception:
        tg_id_value = None
    logger.info(
        "YooKassa webhook received: event=%s payment_id=%s tg_id=%s",
        event_type,
        payment_id,
        tg_id_value or "-",
    )

    amount_obj = obj.get("amount") if isinstance(obj, dict) else {}
    amount_rub = None
    try:
        amount_rub = int(round(float((amount_obj or {}).get("value") or "0")))
    except Exception:
        amount_rub = None
    status = str((obj or {}).get("status") or "pending").strip() or "pending"

    if payment is None and tg_id_value:
        payment = YooKassaPayment(
            tg_id=tg_id_value,
            product=product,
            amount_rub=amount_rub or 5000,
            payment_id=payment_id,
            idempotence_key=f"webhook:{payment_id}",
            status=status,
            confirmation_url=None,
        )
        db.add(payment)
        await db.flush()

    if payment is not None:
        payment.status = status
        if event_type == "payment.succeeded" and payment.paid_at is None:
            payment.paid_at = datetime.now(timezone.utc)
        if not payment.product:
            payment.product = product

    if event_type == "payment.succeeded":
        target_tg_id = int(payment.tg_id) if payment is not None else (tg_id_value or 0)
        if target_tg_id > 0:
            result = await process_game10_payment_success(db=db, payment_id=payment_id, tg_id=target_tg_id)
            logger.info(
                "YooKassa payment succeeded: payment_id=%s tg_id=%s result=%s",
                payment_id,
                target_tg_id,
                result.get("result"),
            )
        else:
            logger.info("YooKassa payment succeeded without tg_id: payment_id=%s", payment_id)

    return {"ok": True}
