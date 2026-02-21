from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.catalog.models import CatalogItem
from core.crm.service import CRMService
from core.integrations.getcourse.getcourse_service import GetCourseService


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


def test_getcourse_mapping_invalid_url_sets_no_link_and_bad_url(monkeypatch):
    monkeypatch.setenv("GETCOURSE_BASE_URL", "https://demo.getcourse.ru")

    service = GetCourseService(db=None)  # type: ignore[arg-type]
    raw = {
        "id": 1001,
        "title": "Онлайн-курс",
        "description": "<p>Описание</p>",
        "url": "https://demo.getcourse.ru/pl/cms/page/view?key=abc",
    }
    dto = service._build_entity("pages", raw)
    assert dto is not None
    assert dto.url is None
    assert dto.url_error == "truncated_key"
    assert dto.url_source == "url"

    mapped = service.normalize_entity_to_catalog_fields(dto)
    assert mapped["link_getcourse"] is None
    assert mapped["url_error"] == "truncated_key"


def test_sync_catalog_counts_bad_url():
    store: dict[tuple[str, str], CatalogItem] = {}
    crm = CRMService(db=_FakeDB(store))  # type: ignore[arg-type]

    async def _get_catalog_by_external(source: str, external_id: str) -> CatalogItem | None:
        return store.get((source, external_id))

    crm._get_catalog_by_external = _get_catalog_by_external  # type: ignore[method-assign]

    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    entity = {
        "title": "Курс",
        "description": "Описание",
        "price": 1000.0,
        "currency": "RUB",
        "link_getcourse": None,
        "url_error": "truncated_key",
        "item_type": "course",
        "status": "active",
        "external_source": "getcourse",
        "external_id": "bad-1",
        "external_updated_at": now,
    }

    result = asyncio.run(
        crm.sync_getcourse_catalog([entity], _FakeIntegration())  # type: ignore[arg-type]
    )
    assert result == {"created": 1, "updated": 0, "skipped": 0, "bad_url": 1}
    assert store[("getcourse", "bad-1")].link_getcourse is None
