from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.deps import get_db
from core.api import payments as payments_api
from core.api.payments import router as payments_router


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


def test_create_yookassa_payment_payload_contains_receipt(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.delenv("YOOKASSA_TAX_SYSTEM_CODE", raising=False)
    monkeypatch.delenv("YOOKASSA_VAT_CODE", raising=False)

    capture: dict = {}
    response = _DummyResponse(
        {
            "id": "yk_test_1",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://pay.example/1"},
        }
    )
    monkeypatch.setattr(
        payments_api.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(response=response, capture=capture),
    )

    result = asyncio.run(
        payments_api._create_yookassa_payment(
            tg_id=123456,
            customer_email="test@example.com",
            customer_phone=None,
        )
    )
    assert result["payment_id"] == "yk_test_1"
    payload = capture["json"]
    assert payload["receipt"]["tax_system_code"] == 2
    assert payload["receipt"]["items"][0]["vat_code"] == 1
    assert payload["receipt"]["items"][0]["payment_subject"] == "service"
    assert payload["receipt"]["items"][0]["payment_mode"] == "full_payment"
    assert payload["receipt"]["customer"]["email"] == "test@example.com"


def test_game10_create_returns_400_when_no_receipt_contacts(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")
    monkeypatch.setattr(
        payments_api,
        "_get_receipt_customer_contact",
        AsyncMock(return_value=(None, None)),
    )

    class _ScalarNoneResult:
        def scalar_one_or_none(self):
            return None

    class _FakeDB:
        async def execute(self, *args, **kwargs):
            return _ScalarNoneResult()

        def add(self, *_args, **_kwargs):
            raise AssertionError("db.add should not be called when contacts are missing")

        async def flush(self):
            raise AssertionError("db.flush should not be called when contacts are missing")

    fake_db = _FakeDB()

    async def _override_db():
        yield fake_db

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/payments")
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    response = client.post(
        "/api/payments/game10/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 123456},
    )
    assert response.status_code == 400
    assert "телефон или email" in response.json()["detail"].lower()
