from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.integrations.getcourse import GetCourseService


router = APIRouter()


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
