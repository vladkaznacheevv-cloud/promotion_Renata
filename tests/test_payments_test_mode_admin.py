from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api import payments as payments_api
from core.api.deps import get_db
from core.api.payments import router as payments_router


class _FakeDB:
    async def execute(self, *_args, **_kwargs):
        return None

    async def flush(self):
        return None

    def add(self, *_args, **_kwargs):
        return None


async def _override_db():
    yield _FakeDB()


def _build_client():
    app = FastAPI()
    app.include_router(payments_router, prefix="/api/payments")
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


def test_test_payment_endpoint_requires_flag_and_admin(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")
    monkeypatch.setenv("PAYMENTS_TEST_ENABLED", "false")
    monkeypatch.setenv("PAYMENTS_TEST_AMOUNT_RUB", "10")
    client = _build_client()

    response = client.post(
        "/api/payments/test/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 123},
    )
    assert response.status_code in {403, 404}

    monkeypatch.setenv("PAYMENTS_TEST_ENABLED", "true")
    monkeypatch.setenv("BOT_ADMIN_IDS", "111,222")
    response = client.post(
        "/api/payments/test/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 333},
    )
    assert response.status_code == 403

    captured: dict = {}

    async def _fake_common(**kwargs):
        captured.update(kwargs)
        return payments_api.Game10PaymentCreateOut(
            payment_id="yk_admin_test_1",
            confirmation_url="https://pay.example/ok",
            amount_rub=int(kwargs["amount_rub"]),
        )

    monkeypatch.setattr(payments_api, "_create_game10_payment_common", _fake_common)
    response = client.post(
        "/api/payments/test/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 111},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["payment_id"] == "yk_admin_test_1"
    assert payload["amount_rub"] == 10
    assert int(captured["amount_rub"]) == 10


def test_main_game10_create_keeps_5000_and_ignores_amount_override(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "bot-token")
    client = _build_client()
    captured: dict = {}

    async def _fake_common(**kwargs):
        captured.update(kwargs)
        return payments_api.Game10PaymentCreateOut(
            payment_id="yk_main_1",
            confirmation_url="https://pay.example/main",
            amount_rub=int(kwargs["amount_rub"]),
        )

    monkeypatch.setattr(payments_api, "_create_game10_payment_common", _fake_common)
    response = client.post(
        "/api/payments/game10/create",
        headers={"X-Bot-Api-Token": "bot-token"},
        json={"tg_id": 111, "amount_rub": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert int(captured["amount_rub"]) == payments_api.GAME10_PRICE_RUB
    assert payload["amount_rub"] == payments_api.GAME10_PRICE_RUB
