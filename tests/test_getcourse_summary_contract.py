from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

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
                    "fetched": 5,
                    "created": 2,
                    "updated": 1,
                    "skipped": 2,
                    "no_date": 1,
                },
                "sourceUrl": "https://getcourse.ru",
                "lastError": None,
                "ok": True,
                "fetched": 5,
                "imported": {"created": 2, "updated": 1, "skipped": 2, "no_date": 1},
                "importedEvents": {"created": 2, "updated": 1, "skipped": 2, "no_date": 1},
                "importedCatalog": {"created": 1, "updated": 1, "skipped": 0},
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
    assert set(data["counts"].keys()) >= {
        "courses",
        "products",
        "events",
        "catalog_items",
        "fetched",
        "created",
        "updated",
        "skipped",
        "no_date",
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
                    "fetched": 6,
                    "created": 1,
                    "updated": 3,
                    "skipped": 2,
                    "no_date": 2,
                },
                "sourceUrl": "https://getcourse.ru",
                "lastError": None,
                "ok": True,
                "fetched": 6,
                "imported": {"created": 1, "updated": 3, "skipped": 2, "no_date": 2},
                "importedEvents": {"created": 1, "updated": 3, "skipped": 2, "no_date": 2},
                "importedCatalog": {"created": 2, "updated": 1, "skipped": 1},
            }
        ),
    )

    app = _build_app()
    client = TestClient(app)

    response = client.post("/api/crm/integrations/getcourse/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["ok"] is True
