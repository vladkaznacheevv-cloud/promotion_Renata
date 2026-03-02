from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("jose")
pytestmark = pytest.mark.integration

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
    list_clients_mock = AsyncMock(
        return_value={
            "items": [
                {
                    "id": 1,
                    "tg_id": 10001,
                    "name": "Test",
                    "telegram": "@test",
                    "status": "New",
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
    )
    monkeypatch.setattr(
        CRMService,
        "list_clients",
        list_clients_mock,
    )
    app = _build_app()
    client = TestClient(app)
    response = client.get("/api/crm/clients?stage=NEW&search=test&limit=25&offset=50")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["stage"] == "NEW"
    list_clients_mock.assert_awaited_once_with(limit=25, offset=50, stage="NEW", search="test")


def test_patch_client_smoke(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "update_client",
        AsyncMock(
            return_value={
                "id": 1,
                "tg_id": 10001,
                "name": "Test",
                "telegram": "@test",
                "status": "New",
                "stage": "READY_TO_PAY",
                "phone": "+79991234567",
                "email": "test@example.com",
                "registered": "2026-01-01",
                "interested": None,
                "aiChats": 3,
                "lastActivity": "2026-02-10T10:00:00",
                "revenue": 0,
                "flags": {"readyToPay": True, "needsManager": False},
            }
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.patch(
        "/api/crm/clients/1",
        json={"stage": "READY_TO_PAY", "phone": "+79991234567", "email": "test@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "READY_TO_PAY"


def test_create_payment_then_mark_paid_smoke(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "create_payment_for_user",
        AsyncMock(
            return_value={
                "id": 10,
                "user_id": 1,
                "client_name": "Test",
                "tg_id": 10001,
                "event_id": 5,
                "event_title": "Event",
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
                "client_name": "Test",
                "tg_id": 10001,
                "event_id": 5,
                "event_title": "Event",
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


def _event_stub(**overrides):
    payload = {
        "id": 1,
        "title": "Test event",
        "type": "Event",
        "price": 4500,
        "attendees": 0,
        "date": None,
        "status": "active",
        "description": "Description",
        "location": "Online",
        "link_getcourse": None,
        "revenue": 0,
        "schedule_type": "recurring",
        "start_date": "2026-09-08",
        "start_time": "17:00",
        "end_time": "21:00",
        "recurring_rule": {"freq": "MONTHLY", "bysetpos": [2, 4], "byweekday": "TU"},
        "occurrence_dates": None,
        "schedule_text": "Start 08.09.2026; 2nd and 4th Tuesday, 17:00-21:00",
        "pricing_options": [{"label": "Session", "price_rub": 4500, "note": None}],
        "hosts": None,
        "price_individual_rub": None,
        "price_group_rub": None,
        "duration_hint": None,
        "booking_hint": None,
    }
    payload.update(overrides)
    return payload


def test_create_event_one_time_without_date_returns_422():
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/crm/events",
        json={
            "title": "One-time",
            "description": "Description",
            "schedule_type": "one_time",
            "date": None,
        },
    )
    assert response.status_code == 422


def test_create_event_rolling_with_date_returns_422():
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/crm/events",
        json={
            "title": "Rolling",
            "description": "Description",
            "schedule_type": "rolling",
            "date": "2026-09-08",
        },
    )
    assert response.status_code == 422


def test_create_event_recurring_without_start_date_returns_422():
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/crm/events",
        json={
            "title": "Recurring",
            "description": "Description",
            "schedule_type": "recurring",
            "recurring_rule": {"freq": "MONTHLY", "bysetpos": [2, 4], "byweekday": "TU"},
        },
    )
    assert response.status_code == 422


def test_create_event_recurring_with_rule_returns_200(monkeypatch):
    monkeypatch.setattr(CRMService, "create_event", AsyncMock(return_value=_event_stub()))
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/crm/events",
        json={
            "title": "Growing up",
            "description": "Description",
            "schedule_type": "recurring",
            "start_date": "2026-09-08",
            "start_time": "17:00",
            "end_time": "21:00",
            "recurring_rule": {"freq": "MONTHLY", "bysetpos": [2, 4], "byweekday": "TU"},
            "pricing_options": [{"label": "Session", "price_rub": 4500}],
        },
    )
    assert response.status_code == 200
    assert response.json()["schedule_type"] == "recurring"


def test_create_event_recurring_with_occurrence_dates_returns_200(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "create_event",
        AsyncMock(
            return_value=_event_stub(
                recurring_rule=None,
                occurrence_dates=["2026-03-27", "2026-04-24", "2026-05-29"],
                schedule_text="Dates: 27.03, 24.04, 29.05; 10:00-18:00",
                start_time="10:00",
                end_time="18:00",
            )
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/crm/events",
        json={
            "title": "Supervisor group",
            "description": "Description",
            "schedule_type": "recurring",
            "start_date": "2026-03-01",
            "start_time": "10:00",
            "end_time": "18:00",
            "occurrence_dates": ["2026-03-27", "2026-04-24", "2026-05-29"],
            "pricing_options": [{"label": "Price", "price_rub": 6000}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["occurrence_dates"] == ["2026-03-27", "2026-04-24", "2026-05-29"]
