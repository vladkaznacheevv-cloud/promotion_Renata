from __future__ import annotations

import asyncio

from core.api import payments as payments_api


class _DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _DummyAsyncClient:
    def __init__(self, *, response: _DummyResponse, capture: dict) -> None:
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None, auth=None):
        self._capture["url"] = url
        self._capture["json"] = json
        self._capture["headers"] = headers
        self._capture["auth"] = auth
        return self._response


def test_yookassa_payload_contains_notification_url_and_receipt(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "whsec_test")
    monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", "2")
    monkeypatch.setenv("YOOKASSA_VAT_CODE", "1")

    capture: dict = {}
    monkeypatch.setattr(
        payments_api.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(
            response=_DummyResponse(
                {
                    "id": "pay_123",
                    "status": "pending",
                    "confirmation": {"confirmation_url": "https://pay.example/confirm"},
                }
            ),
            capture=capture,
        ),
    )

    asyncio.run(
        payments_api._create_yookassa_payment(
            tg_id=12345,
            customer_email="user@example.com",
            customer_phone="+79991234567",
        )
    )

    payload = capture["json"]
    assert payload["notification_url"] == "https://api.example.com/api/webhooks/yookassa/whsec_test"
    assert payload["receipt"]["tax_system_code"] == 2
    assert payload["receipt"]["items"][0]["vat_code"] == 1


def test_yookassa_notification_url_adds_https_scheme_when_missing(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "api.example.com")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "whsec_test")
    assert (
        payments_api._yookassa_notification_url()
        == "https://api.example.com/api/webhooks/yookassa/whsec_test"
    )
