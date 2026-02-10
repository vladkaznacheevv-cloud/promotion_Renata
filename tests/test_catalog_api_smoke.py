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


def test_get_catalog_contract(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "list_catalog",
        AsyncMock(
            return_value={
                "items": [
                    {
                        "id": 1,
                        "title": "Курс по продажам",
                        "description": "Описание",
                        "price": 7900,
                        "currency": "RUB",
                        "link_getcourse": "https://example.com/course",
                        "item_type": "course",
                        "status": "active",
                        "external_source": "getcourse",
                        "external_id": "gc-1",
                        "external_updated_at": "2026-02-10T10:00:00",
                        "updated_at": "2026-02-10T10:00:00",
                    }
                ],
                "total": 1,
            }
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.get("/api/crm/catalog?type=course&search=sales&limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["item_type"] == "course"
    assert "link_getcourse" in data["items"][0]


def test_get_catalog_item_contract(monkeypatch):
    monkeypatch.setattr(
        CRMService,
        "get_catalog_item",
        AsyncMock(
            return_value={
                "id": 2,
                "title": "Продукт",
                "description": "Описание продукта",
                "price": 3900,
                "currency": "RUB",
                "link_getcourse": "https://example.com/product",
                "item_type": "product",
                "status": "active",
                "external_source": "getcourse",
                "external_id": "gc-2",
                "external_updated_at": "2026-02-10T10:00:00",
                "updated_at": "2026-02-10T10:00:00",
            }
        ),
    )
    app = _build_app()
    client = TestClient(app)
    response = client.get("/api/crm/catalog/2")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["item_type"] == "product"
