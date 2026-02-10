from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("jose")

from core.api.deps import get_db
from core.auth.deps import get_current_admin_user
from core.crm.api import router as crm_router
from core.crm.service import CRMService


async def _override_db():
    yield None


async def _override_user():
    return SimpleNamespace(id=1, role="admin", is_active=True)


def _build_app():
    app = FastAPI()
    app.include_router(crm_router, prefix="/api/crm")
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_admin_user] = _override_user
    return app


def test_get_clients_smoke(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "list_clients",
        AsyncMock(
            return_value={
                "items": [
                    {
                        "id": 1,
                        "tg_id": 10001,
                        "name": "Тест",
                        "telegram": "@test",
                        "status": "Новый",
                        "stage": "NEW",
                        "phone": None,
                        "email": None,
                        "registered": "2026-01-01",
                        "interested": None,
                        "aiChats": 0,
                        "lastActivity": None,
                        "revenue": 0,
                        "flags": {"readyToPay": False, "needsManager": False},
                    }
                ],
                "total": 1,
            }
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.get("/api/crm/clients?stage=NEW&search=test")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["stage"] == "NEW"


def test_patch_client_smoke(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "update_client",
        AsyncMock(
            return_value={
                "id": 1,
                "tg_id": 10001,
                "name": "Тест",
                "telegram": "@test",
                "status": "Новый",
                "stage": "MANAGER_FOLLOWUP",
                "phone": "+79991234567",
                "email": "test@example.com",
                "registered": "2026-01-01",
                "interested": None,
                "aiChats": 3,
                "lastActivity": "2026-02-10T10:00:00",
                "revenue": 0,
                "flags": {"readyToPay": True, "needsManager": True},
            }
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.patch(
        "/api/crm/clients/1",
        json={"stage": "MANAGER_FOLLOWUP", "phone": "+79991234567", "email": "test@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "MANAGER_FOLLOWUP"


def test_create_payment_then_mark_paid_smoke(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "create_payment_for_user",
        AsyncMock(
            return_value={
                "id": 10,
                "user_id": 1,
                "client_name": "Тест",
                "tg_id": 10001,
                "event_id": 5,
                "event_title": "Событие",
                "amount": 1000,
                "currency": "RUB",
                "status": "pending",
                "source": "yookassa",
                "created_at": "2026-02-10T10:00:00",
                "paid_at": None,
            }
        ),
    )
    monkeypatch.setattr(
        CRMService,
        "mark_payment_status",
        AsyncMock(
            return_value={
                "id": 10,
                "user_id": 1,
                "client_name": "Тест",
                "tg_id": 10001,
                "event_id": 5,
                "event_title": "Событие",
                "amount": 1000,
                "currency": "RUB",
                "status": "paid",
                "source": "yookassa",
                "created_at": "2026-02-10T10:00:00",
                "paid_at": "2026-02-10T10:05:00",
            }
        ),
    )

    app = _build_app()
    client = TestClient(app)
    create_res = client.post(
        "/api/crm/payments",
        json={"user_id": 1, "event_id": 5, "amount": 1000, "currency": "RUB", "source": "yookassa"},
    )
    assert create_res.status_code == 200
    assert create_res.json()["status"] == "pending"

    mark_res = client.patch("/api/crm/payments/10", json={"status": "paid"})
    assert mark_res.status_code == 200
    assert mark_res.json()["status"] == "paid"
