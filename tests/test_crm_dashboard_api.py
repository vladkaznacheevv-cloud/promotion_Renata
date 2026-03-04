from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def test_dashboard_endpoint_accepts_only_supported_days(monkeypatch):
    summary_mock = AsyncMock(
        return_value={
            "days": 30,
            "start_ts": datetime(2026, 2, 3, tzinfo=timezone.utc),
            "end_ts": datetime(2026, 3, 4, tzinfo=timezone.utc),
            "ai_answers": 12,
            "new_clients": 5,
            "payments_count": 2,
            "revenue_total": 10000,
        }
    )
    monkeypatch.setattr(CRMService, "get_dashboard_summary", summary_mock)
    client = TestClient(_build_app())

    ok_response = client.get("/api/crm/dashboard?days=30")
    assert ok_response.status_code == 200
    assert ok_response.json()["days"] == 30
    summary_mock.assert_awaited_once_with(days=30)

    bad_response = client.get("/api/crm/dashboard?days=15")
    assert bad_response.status_code == 422
