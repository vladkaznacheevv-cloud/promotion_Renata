from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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


def test_create_yookassa_payment_payload_contains_notification_url(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "whsec_test")

    capture: dict = {}
    response = _DummyResponse(
        {
            "id": "yk_test_2",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://pay.example/2"},
        }
    )
    monkeypatch.setattr(
        payments_api.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(response=response, capture=capture),
    )

    asyncio.run(
        payments_api._create_yookassa_payment(
            tg_id=123456,
            customer_email="test@example.com",
            customer_phone=None,
        )
    )
    payload = capture["json"]
    assert payload["notification_url"] == "https://api.example.com/api/webhooks/yookassa/whsec_test"

def test_create_yookassa_test_payment_payload_uses_amount_50_and_test_product(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")

    capture: dict = {}
    response = _DummyResponse(
        {
            "id": "yk_test_50",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://pay.example/50"},
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
            amount_rub=50,
            product_code="game10_test",
            payment_description="Game10 test payment",
            receipt_item_description="Game10 test payment",
        )
    )
    assert result["payment_id"] == "yk_test_50"
    payload = capture["json"]
    assert payload["amount"]["value"] == "50.00"
    assert payload["metadata"]["product"] == "game10_test"
    assert payload["receipt"]["items"][0]["amount"]["value"] == "50.00"
    assert payload["receipt"]["items"][0]["description"] == "Game10 test payment"



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
    detail = response.json()["detail"].lower()
    assert "email" in detail
    assert ("phone" in detail) or ("телефон" in detail)



def test_should_reuse_existing_payment_when_fresh_and_pending(monkeypatch):
    monkeypatch.setenv("YOOKASSA_REUSE_TTL_MINUTES", "15")
    existing = SimpleNamespace(
        payment_id="pay_1",
        confirmation_url="https://pay.example/1",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    monkeypatch.setattr(
        payments_api,
        "_get_yookassa_payment_status",
        AsyncMock(return_value="pending"),
    )
    can_reuse, reason = asyncio.run(payments_api._should_reuse_existing_game10_payment(existing))
    assert can_reuse is True
    assert reason == "fresh"


def test_should_not_reuse_existing_payment_when_expired_ttl(monkeypatch):
    monkeypatch.setenv("YOOKASSA_REUSE_TTL_MINUTES", "15")
    existing = SimpleNamespace(
        payment_id="pay_2",
        confirmation_url="https://pay.example/2",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    status_mock = AsyncMock(return_value="pending")
    monkeypatch.setattr(payments_api, "_get_yookassa_payment_status", status_mock)
    can_reuse, reason = asyncio.run(payments_api._should_reuse_existing_game10_payment(existing))
    assert can_reuse is False
    assert reason == "expired_ttl"
    assert status_mock.await_count == 0


def test_should_not_reuse_existing_payment_when_status_canceled(monkeypatch):
    monkeypatch.setenv("YOOKASSA_REUSE_TTL_MINUTES", "15")
    existing = SimpleNamespace(
        payment_id="pay_3",
        confirmation_url="https://pay.example/3",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
    )
    monkeypatch.setattr(
        payments_api,
        "_get_yookassa_payment_status",
        AsyncMock(return_value="canceled"),
    )
    can_reuse, reason = asyncio.run(payments_api._should_reuse_existing_game10_payment(existing))
    assert can_reuse is False
    assert reason == "status_not_pending"


def test_game10_test_endpoint_uses_test_product_and_amount(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")

    calls: list[dict] = []

    async def _fake_existing(db, *, tg_id, product_code, amount_rub):
        calls.append({"tg_id": tg_id, "product_code": product_code, "amount_rub": amount_rub})
        return None

    monkeypatch.setattr(payments_api, "_get_last_pending_game10_payment", _fake_existing)
    monkeypatch.setattr(payments_api, "_get_receipt_customer_contact", AsyncMock(return_value=("test@example.com", None)))
    class _DummyYooKassaPayment:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    monkeypatch.setattr(payments_api, "YooKassaPayment", _DummyYooKassaPayment)
    monkeypatch.setattr(
        payments_api,
        "_create_yookassa_payment",
        AsyncMock(
            return_value={
                "payment_id": "yk_test_create",
                "confirmation_url": "https://pay.example/test",
                "status": "pending",
                "idempotence_key": "idem-test",
            }
        ),
    )

    class _FakeDB:
        def __init__(self) -> None:
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def flush(self):
            return None

    fake_db = _FakeDB()

    async def _override_db():
        yield fake_db

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/payments")
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    response = client.post(
        "/api/payments/game10/test/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 123456},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["amount_rub"] == 50
    assert calls and calls[0]["product_code"] == "game10_test"
    assert calls[0]["amount_rub"] == 50
    assert fake_db.added and getattr(fake_db.added[0], "product", None) == "game10_test"
    assert getattr(fake_db.added[0], "amount_rub", None) == 50


def test_reuse_lookup_is_separated_for_main_and_test_endpoints(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")

    calls: list[tuple[str, int]] = []

    async def _fake_existing(db, *, tg_id, product_code, amount_rub):
        calls.append((product_code, amount_rub))
        return None

    monkeypatch.setattr(payments_api, "_get_last_pending_game10_payment", _fake_existing)
    monkeypatch.setattr(payments_api, "_get_receipt_customer_contact", AsyncMock(return_value=("test@example.com", None)))
    class _DummyYooKassaPayment:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    monkeypatch.setattr(payments_api, "YooKassaPayment", _DummyYooKassaPayment)
    monkeypatch.setattr(
        payments_api,
        "_create_yookassa_payment",
        AsyncMock(return_value={"payment_id": "yk_any", "confirmation_url": "https://pay.example/any", "status": "pending", "idempotence_key": "idem-any"}),
    )

    class _FakeDB:
        def add(self, obj):
            return None

        async def flush(self):
            return None

    fake_db = _FakeDB()

    async def _override_db():
        yield fake_db

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/payments")
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    r_main = client.post("/api/payments/game10/create", headers={"X-Bot-Api-Token": "bot-token"}, json={"tg_id": 1})
    r_test = client.post("/api/payments/game10/test/create", headers={"X-Bot-Api-Token": "bot-token"}, json={"tg_id": 1})
    assert r_main.status_code == 200
    assert r_test.status_code == 200
    assert ("game10", 5000) in calls
    assert ("game10_test", 50) in calls


def test_yookassa_status_endpoint_checks_remote_status_and_processes_success(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")
    payment_obj = SimpleNamespace(
        payment_id="yk_status_1",
        tg_id=123456,
        status="pending",
        paid_at=None,
    )

    class _ScalarPaymentResult:
        def scalar_one_or_none(self):
            return payment_obj

    class _FakeDB:
        async def execute(self, *args, **kwargs):
            return _ScalarPaymentResult()

        async def flush(self):
            return None

    fake_db = _FakeDB()
    monkeypatch.setattr(payments_api, "_get_yookassa_payment_status", AsyncMock(return_value="succeeded"))
    monkeypatch.setattr(
        payments_api,
        "process_game10_payment_success",
        AsyncMock(return_value={"result": "invite_sent", "already_in_channel": False}),
    )

    async def _override_db():
        yield fake_db

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/payments")
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    response = client.post(
        "/api/payments/yookassa/status",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"payment_id": "yk_status_1"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["payment_id"] == "yk_status_1"
    assert payload["status"] == "succeeded"
    assert payload["processed_success"] is True
    assert payload["result"] == "invite_sent"
