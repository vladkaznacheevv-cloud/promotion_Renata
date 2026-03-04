from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.deps import get_db
from core.api.webhooks import router as webhooks_router


class _ScalarNoneResult:
    def scalar_one_or_none(self):
        return None


class _FakeDB:
    def add(self, _obj):
        return None

    async def flush(self):
        return None

    async def rollback(self):
        return None

    async def execute(self, *_args, **_kwargs):
        return _ScalarNoneResult()


async def _override_db():
    yield _FakeDB()


def _build_app():
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/api/webhooks")
    app.dependency_overrides[get_db] = _override_db
    return app


def test_yookassa_webhook_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "valid-token")
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/yookassa/wrong-token",
        json={"event": "payment.succeeded", "object": {"id": "yk_1"}},
    )
    assert response.status_code == 401


def test_yookassa_webhook_accepts_valid_payload_and_logs_request_id(monkeypatch, caplog):
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "valid-token")
    app = _build_app()
    client = TestClient(app)
    caplog.set_level("INFO", logger="core.api.webhooks")

    response = client.post(
        "/api/webhooks/yookassa/valid-token",
        headers={"X-Request-Id": "req-123"},
        json={
            "event": "payment.waiting_for_capture",
            "object": {"id": "yk_2", "status": "pending"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert any(
        "request_id=req-123" in record.getMessage() and "status=200" in record.getMessage()
        for record in caplog.records
    )
