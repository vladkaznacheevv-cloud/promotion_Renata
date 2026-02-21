from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import core.consultations.models  # noqa: F401  (register SQLAlchemy relationships)

from core.crm.service import CRMService
from core.events.models import Event


class _FakeDB:
    def __init__(self, store: dict[tuple[str, str], Event]) -> None:
        self._store = store

    def add(self, event: Event) -> None:
        key = (str(event.external_source or ""), str(event.external_id or ""))
        self._store[key] = event

    async def flush(self) -> None:
        return None


class _FakeIntegration:
    @staticmethod
    def normalize_entity_to_event_fields(entity: dict) -> dict:
        return entity


def _entity(
    *,
    external_id: str,
    title: str = "Курс по продажам",
    description: str = "Описание курса",
    starts_at: datetime | None = None,
    price: float | None = 1200.0,
) -> dict:
    dt = starts_at or datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    status = "finished" if dt < datetime.now(tz=timezone.utc) else "active"
    return {
        "title": title,
        "description": description,
        "location": "Онлайн",
        "link_getcourse": "https://getcourse.ru/pl/teach/control/lesson/view?id=123",
        "price": price,
        "status": status,
        "date": dt.date(),
        "starts_at": dt,
        "external_source": "getcourse",
        "external_id": external_id,
        "external_updated_at": dt,
    }


def test_sync_getcourse_events_upsert_idempotent_and_no_date():
    store: dict[tuple[str, str], Event] = {}
    service = CRMService(db=_FakeDB(store))  # type: ignore[arg-type]

    async def _get_event_by_external(source: str, external_id: str) -> Event | None:
        return store.get((source, external_id))

    service._get_event_by_external = _get_event_by_external  # type: ignore[method-assign]
    integration = _FakeIntegration()

    first = asyncio.run(
        service.sync_getcourse_events([_entity(external_id="42")], integration)  # type: ignore[arg-type]
    )
    assert first == {"created": 1, "updated": 0, "skipped": 0, "no_date": 0, "bad_url": 0}
    assert len(store) == 1

    second = asyncio.run(
        service.sync_getcourse_events([_entity(external_id="42")], integration)  # type: ignore[arg-type]
    )
    assert second == {"created": 0, "updated": 0, "skipped": 1, "no_date": 0, "bad_url": 0}
    assert len(store) == 1

    third = asyncio.run(
        service.sync_getcourse_events(
            [_entity(external_id="42", description="Обновлённое описание")],
            integration,  # type: ignore[arg-type]
        )
    )
    assert third == {"created": 0, "updated": 1, "skipped": 0, "no_date": 0, "bad_url": 0}
    saved = store[("getcourse", "42")]
    assert saved.description == "Обновлённое описание"
    assert saved.price == Decimal("1200.0")

    no_date_entity = _entity(external_id="100")
    no_date_entity["date"] = None
    no_date_entity["starts_at"] = None
    fourth = asyncio.run(
        service.sync_getcourse_events([no_date_entity], integration)  # type: ignore[arg-type]
    )
    assert fourth == {"created": 0, "updated": 0, "skipped": 0, "no_date": 1, "bad_url": 0}
    assert ("getcourse", "100") not in store
