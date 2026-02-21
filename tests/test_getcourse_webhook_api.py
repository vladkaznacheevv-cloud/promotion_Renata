from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.deps import get_db
from core.api.webhooks import router as webhooks_router
from core.integrations.getcourse.getcourse_service import GetCourseService


class _DummyDB:
    async def commit(self):
        return None


async def _override_db():
    yield _DummyDB()


def _build_app():
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/api/webhooks")
    app.dependency_overrides[get_db] = _override_db
    return app


def test_getcourse_webhook_auth(monkeypatch):
    monkeypatch.setenv("GETCOURSE_WEBHOOK_TOKEN", "secret-token")
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/getcourse",
        headers={"X-Webhook-Token": "wrong"},
        json={"event_type": "payment"},
    )
    assert response.status_code == 401


def test_getcourse_webhook_store_event(monkeypatch):
    monkeypatch.setenv("GETCOURSE_WEBHOOK_TOKEN", "secret-token")
    captured: list[dict] = []

    async def _store(self, payload):  # noqa: ANN001
        captured.append(payload)
        return SimpleNamespace(id=1)

    monkeypatch.setattr(GetCourseService, "store_webhook_event", _store)
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/getcourse",
        headers={"X-Webhook-Token": "secret-token"},
        json={"event_type": "payment", "user_email": "test@example.com"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured and captured[0]["event_type"] == "payment"


def test_getcourse_webhook_bearer_auth(monkeypatch):
    monkeypatch.setenv("GETCOURSE_WEBHOOK_TOKEN", "secret-token")
    captured: list[dict] = []

    async def _store(self, payload):  # noqa: ANN001
        captured.append(payload)
        return SimpleNamespace(id=1)

    monkeypatch.setattr(GetCourseService, "store_webhook_event", _store)
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/getcourse",
        headers={"Authorization": "Bearer secret-token"},
        json={"event_type": "payment"},
    )
    assert response.status_code == 200
    assert captured and captured[0]["event_type"] == "payment"


def test_getcourse_summary_counts(monkeypatch):
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalar_one(self):
            return self._value

    class _FakeDB:
        def __init__(self):
            self._values = iter(
                [
                    datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc),  # last_event_at
                    3,  # 24h
                    11,  # 7d
                ]
            )

        async def execute(self, *_args, **_kwargs):
            return _Result(next(self._values))

    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_BASE_URL", "https://renataminakova.getcourse.ru")
    monkeypatch.delenv("GETCOURSE_API_KEY", raising=False)

    service = GetCourseService(db=_FakeDB())  # type: ignore[arg-type]

    async def _state():
        return SimpleNamespace(last_sync_at=None, last_error=None)

    service._state = _state  # type: ignore[method-assign]
    summary = asyncio.run(service.summary())
    assert summary["enabled"] is True
    assert summary["events_last_24h"] == 3
    assert summary["events_last_7d"] == 11
    assert summary["last_event_at"] is not None
