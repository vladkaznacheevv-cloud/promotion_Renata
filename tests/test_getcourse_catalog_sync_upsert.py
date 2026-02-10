from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from core.catalog.models import CatalogItem
from core.crm.service import CRMService


class _FakeDB:
    def __init__(self, store: dict[tuple[str, str], CatalogItem]) -> None:
        self._store = store

    def add(self, item: CatalogItem) -> None:
        key = (str(item.external_source or ""), str(item.external_id or ""))
        self._store[key] = item

    async def flush(self) -> None:
        return None


class _FakeIntegration:
    @staticmethod
    def normalize_entity_to_catalog_fields(entity: dict) -> dict:
        return entity


def _item(
    *,
    external_id: str,
    title: str = "Курс по продажам",
    description: str = "Описание курса",
    link_getcourse: str | None = "https://example.com/course",
    price: float | None = 7900.0,
) -> dict:
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    return {
        "title": title,
        "description": description,
        "price": price,
        "currency": "RUB",
        "link_getcourse": link_getcourse,
        "item_type": "course",
        "status": "active",
        "external_source": "getcourse",
        "external_id": external_id,
        "external_updated_at": now,
    }


def test_sync_getcourse_catalog_upsert_idempotent_and_updates():
    store: dict[tuple[str, str], CatalogItem] = {}
    service = CRMService(db=_FakeDB(store))  # type: ignore[arg-type]

    async def _get_catalog_by_external(source: str, external_id: str) -> CatalogItem | None:
        return store.get((source, external_id))

    service._get_catalog_by_external = _get_catalog_by_external  # type: ignore[method-assign]
    integration = _FakeIntegration()

    first = asyncio.run(
        service.sync_getcourse_catalog([_item(external_id="42")], integration)  # type: ignore[arg-type]
    )
    assert first == {"created": 1, "updated": 0, "skipped": 0}
    assert len(store) == 1

    second = asyncio.run(
        service.sync_getcourse_catalog([_item(external_id="42")], integration)  # type: ignore[arg-type]
    )
    assert second == {"created": 0, "updated": 0, "skipped": 1}
    assert len(store) == 1

    third = asyncio.run(
        service.sync_getcourse_catalog(
            [_item(external_id="42", description="Новое описание", price=8900.0)],
            integration,  # type: ignore[arg-type]
        )
    )
    assert third == {"created": 0, "updated": 1, "skipped": 0}
    saved = store[("getcourse", "42")]
    assert saved.description == "Новое описание"
    assert saved.price == Decimal("8900.0")


def test_sync_getcourse_catalog_accepts_missing_url():
    store: dict[tuple[str, str], CatalogItem] = {}
    service = CRMService(db=_FakeDB(store))  # type: ignore[arg-type]

    async def _get_catalog_by_external(source: str, external_id: str) -> CatalogItem | None:
        return store.get((source, external_id))

    service._get_catalog_by_external = _get_catalog_by_external  # type: ignore[method-assign]
    integration = _FakeIntegration()

    result = asyncio.run(
        service.sync_getcourse_catalog(
            [_item(external_id="43", link_getcourse=None)],
            integration,  # type: ignore[arg-type]
        )
    )
    assert result == {"created": 1, "updated": 0, "skipped": 0}
    assert store[("getcourse", "43")].link_getcourse is None
