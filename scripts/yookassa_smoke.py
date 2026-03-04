from __future__ import annotations

import argparse
import os
from typing import Any


def _mask_bool(value: str | None) -> bool:
    return bool((value or "").strip())


def _notification_url() -> str | None:
    base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    token = (os.getenv("YOOKASSA_WEBHOOK_TOKEN") or "").strip()
    if not base or not token:
        return None
    return f"{base}/api/webhooks/yookassa/{token}"


def _env_summary() -> dict[str, Any]:
    return {
        "has_public_base_url": _mask_bool(os.getenv("PUBLIC_BASE_URL")),
        "has_yookassa_shop_id": _mask_bool(os.getenv("YOOKASSA_SHOP_ID")),
        "has_yookassa_secret_key": _mask_bool(os.getenv("YOOKASSA_SECRET_KEY")),
        "has_yookassa_webhook_token": _mask_bool(os.getenv("YOOKASSA_WEBHOOK_TOKEN")),
        "has_bot_api_token": _mask_bool(os.getenv("BOT_API_TOKEN")),
        "tax_system_code": (os.getenv("YOOKASSA_TAX_SYSTEM_CODE") or "2").strip() or "2",
        "vat_code": (os.getenv("YOOKASSA_VAT_CODE") or "1").strip() or "1",
    }


async def _call_create_payment(base_url: str, tg_id: int) -> dict[str, Any]:
    import httpx

    bot_api_token = (os.getenv("BOT_API_TOKEN") or "").strip()
    if not bot_api_token:
        raise RuntimeError("BOT_API_TOKEN is not configured")
    url = f"{base_url.rstrip('/')}/api/payments/game10/create"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            url,
            headers={"X-Bot-Api-Token": bot_api_token},
            json={"tg_id": tg_id},
        )
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": (response.text or "")[:500]}
    return {"status_code": response.status_code, "payload": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="YooKassa game10 smoke (env + optional create-payment call).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--tg-id", type=int, default=None, help="Telegram user id for create-payment call")
    args = parser.parse_args()

    print("YooKassa smoke (no secrets printed)")
    for k, v in _env_summary().items():
        print(f"{k}={v}")
    print(f"notification_url={_notification_url() or '<not configured>'}")

    if args.tg_id is None:
        print("skipped: create-payment call (pass --tg-id <TG_ID> to test local backend endpoint)")
        return 0

    import asyncio

    result = asyncio.run(_call_create_payment(args.base_url, args.tg_id))
    status_code = int(result["status_code"])
    payload = result["payload"] if isinstance(result["payload"], dict) else {}
    if status_code != 200:
        print(f"ERROR: create-payment failed with HTTP {status_code}")
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if detail is not None:
            print(f"detail={detail}")
        return 1
    print("OK: payment created")
    print(f"payment_id={payload.get('payment_id')}")
    print(f"confirmation_url={payload.get('confirmation_url')}")
    print(f"amount_rub={payload.get('amount_rub')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
