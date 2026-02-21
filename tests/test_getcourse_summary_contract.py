from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

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


def test_getcourse_summary_contract(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "get_getcourse_summary",
        AsyncMock(
            return_value={
                "enabled": True,
                "status": "OK",
                "lastSyncAt": "2026-02-10T10:00:00",
                "last_sync_at": "2026-02-10T10:00:00",
                "counts": {
                    "courses": 3,
                    "products": 3,
                    "events": 3,
                    "catalog_items": 4,
                    "users": 5,
                    "payments": 6,
                    "fetched": 5,
                    "created": 2,
                    "updated": 1,
                    "skipped": 2,
                    "no_date": 1,
                    "bad_url": 1,
                },
                "sourceUrl": "https://getcourse.ru",
                "lastError": None,
                "ok": True,
                "fetched": 5,
                "imported": {"created": 2, "updated": 1, "skipped": 2, "no_date": 1, "bad_url": 1},
                "importedEvents": {"created": 2, "updated": 1, "skipped": 2, "no_date": 1, "bad_url": 1},
                "importedCatalog": {"created": 1, "updated": 1, "skipped": 0, "bad_url": 0},
                "importedUsers": {"created": 3, "updated": 2, "skipped": 1},
                "importedPayments": {"created": 4, "updated": 1, "skipped": 1},
                "syncAtByResource": {
                    "users": "2026-02-10T10:00:00+00:00",
                    "payments": "2026-02-10T10:00:00+00:00",
                    "catalog": "2026-02-10T10:00:00+00:00",
                },
                "unsupportedResources": ["transactions", "products"],
            }
        ),
    )

    app = _build_app()
    client = TestClient(app)

    response = client.get("/api/crm/integrations/getcourse/summary")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "status" in data
    assert "lastSyncAt" in data
    assert "last_sync_at" in data
    assert "counts" in data
    assert "imported" in data
    assert "importedCatalog" in data
    assert "unsupportedResources" in data
    assert set(data["counts"].keys()) >= {
        "courses",
        "products",
        "events",
        "catalog_items",
        "users",
        "payments",
        "fetched",
        "created",
        "updated",
        "skipped",
        "no_date",
        "bad_url",
    }


def test_getcourse_sync_contract(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "sync_getcourse",
        AsyncMock(
            return_value={
                "enabled": True,
                "status": "OK",
                "lastSyncAt": "2026-02-10T10:10:00",
                "last_sync_at": "2026-02-10T10:10:00",
                "counts": {
                    "courses": 4,
                    "products": 4,
                    "events": 4,
                    "catalog_items": 6,
                    "users": 7,
                    "payments": 8,
                    "fetched": 6,
                    "created": 1,
                    "updated": 3,
                    "skipped": 2,
                    "no_date": 2,
                    "bad_url": 2,
                },
                "sourceUrl": "https://getcourse.ru",
                "lastError": None,
                "ok": True,
                "fetched": 6,
                "imported": {"created": 1, "updated": 3, "skipped": 2, "no_date": 2, "bad_url": 2},
                "importedEvents": {"created": 1, "updated": 3, "skipped": 2, "no_date": 2, "bad_url": 2},
                "importedCatalog": {"created": 2, "updated": 1, "skipped": 1, "bad_url": 0},
                "importedUsers": {"created": 3, "updated": 2, "skipped": 2},
                "importedPayments": {"created": 3, "updated": 2, "skipped": 1},
                "syncAtByResource": {
                    "users": "2026-02-10T10:10:00+00:00",
                    "payments": "2026-02-10T10:10:00+00:00",
                    "catalog": "2026-02-10T10:10:00+00:00",
                },
                "unsupportedResources": ["transactions", "products"],
            }
        ),
    )

    app = _build_app()
    client = TestClient(app)

    response = client.post("/api/crm/integrations/getcourse/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["ok"] is True


def test_getcourse_ping_contract(monkeypatch):
    class _FakeIntegration:
        async def ping_export(self):
            return {
                "enabled": True,
                "base_url": "https://example.getcourse.ru",
                "account_name": "example",
                "api_key_present": True,
                "api_key_len": 96,
                "probe": {"ok": True, "resource": "users", "export_id": "123"},
            }

    monkeypatch.setattr(CRMService, "get_getcourse_integration", lambda _self: _FakeIntegration())
    app = _build_app()
    client = TestClient(app)

    response = client.get("/api/crm/integrations/getcourse/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["api_key_present"] is True
    assert isinstance(data["api_key_len"], int)
    assert "api_key" not in data
    assert data["probe"]["ok"] is True


def test_getcourse_diagnose_contract(monkeypatch):
    class _FakeIntegration:
        async def diagnose_resources(self):
            return {
                "enabled": True,
                "has_key": True,
                "base_url": "https://example.getcourse.ru",
                "resourceStatuses": {
                    "users": {"ok": True, "status_code": 200, "error_kind": None},
                    "transactions": {"ok": False, "status_code": 404, "error_kind": "unsupported"},
                },
                "unsupportedResources": ["transactions"],
                "fatalAuthError": False,
                "successfulResources": ["users"],
            }

    monkeypatch.setattr(CRMService, "get_getcourse_integration", lambda _self: _FakeIntegration())
    app = _build_app()
    client = TestClient(app)

    response = client.get("/api/crm/integrations/getcourse/diagnose")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {
        "enabled",
        "has_key",
        "base_url",
        "resourceStatuses",
        "unsupportedResources",
        "fatalAuthError",
        "successfulResources",
    }
    assert data["enabled"] is True
    assert data["has_key"] is True
    assert data["base_url"].startswith("https://")
    assert "resourceStatuses" in data
    assert "unsupportedResources" in data


def test_getcourse_diagnose_route_registered():
    from core.main import app

    paths = {route.path for route in app.routes}
    assert "/api/crm/integrations/getcourse/diagnose" in paths
