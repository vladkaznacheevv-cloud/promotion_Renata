from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse, urljoin

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.models import IntegrationState
from .getcourse_client import GetCourseClient

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"\s+")


@dataclass
class GetCourseEntityDTO:
    external_id: str
    entity_type: str
    title: str
    description: str | None
    url: str | None
    price: float | None
    start_at: datetime | None
    updated_at: datetime | None
    raw: dict[str, Any]


@dataclass
class GetCourseService:
    db: AsyncSession

    def __post_init__(self) -> None:
        self.client = GetCourseClient()

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    async def _state(self) -> IntegrationState:
        row = await self.db.execute(
            select(IntegrationState).where(IntegrationState.name == "getcourse")
        )
        state = row.scalar_one_or_none()
        if state is not None:
            return state

        state = IntegrationState(name="getcourse")
        self.db.add(state)
        await self.db.flush()
        return state

    @staticmethod
    def _extract_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in data and data.get(key) not in (None, ""):
                return data.get(key)
        return None

    @staticmethod
    def _to_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
            try:
                if fmt is None:
                    parsed = datetime.fromisoformat(text)
                else:
                    parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception:
                continue
        return None

    @staticmethod
    def _to_price(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(" ", "").replace(",", ".")
        try:
            return float(text)
        except Exception:
            return None

    @staticmethod
    def _clean_html(value: Any, max_len: int = 8000) -> str | None:
        if value in (None, ""):
            return None
        text = str(value)
        text = unescape(text)
        text = _HTML_TAG_RE.sub(" ", text)
        text = _MULTISPACE_RE.sub(" ", text).strip()
        if not text:
            return None
        if len(text) > max_len:
            text = text[:max_len].rstrip()
        return text

    def _normalize_url(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        raw = str(value).strip()
        if not raw:
            return None
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return raw
        if raw.startswith("/"):
            return urljoin(f"{self.client.base_url}/", raw.lstrip("/"))
        return None

    def _build_entity(self, source: str, raw: dict[str, Any]) -> GetCourseEntityDTO | None:
        external_id_raw = self._extract_value(raw, ("id", "deal_id", "product_id", "course_id", "webinar_id", "page_id"))
        if external_id_raw in (None, ""):
            return None
        external_id = str(external_id_raw)

        title = self._extract_value(raw, ("title", "name", "deal_title", "product_title", "course_title", "webinar_title"))
        title = str(title).strip() if title not in (None, "") else None
        if not title:
            return None

        description_raw = self._extract_value(raw, ("description", "text", "content", "body", "offer_description"))
        description = self._clean_html(description_raw)
        link = self._normalize_url(self._extract_value(raw, ("url", "link", "public_url", "landing_url", "href")))
        price = self._to_price(self._extract_value(raw, ("price", "amount", "sum", "cost", "offer_price")))
        start_at = self._to_datetime(self._extract_value(raw, ("start_at", "starts_at", "date_start", "start_date", "webinar_date", "date")))
        updated_at = self._to_datetime(self._extract_value(raw, ("updated_at", "modified_at", "updated", "changed_at")))

        return GetCourseEntityDTO(
            external_id=external_id,
            entity_type=source,
            title=title,
            description=description,
            url=link,
            price=price,
            start_at=start_at,
            updated_at=updated_at,
            raw=raw,
        )

    async def fetch_entities(self) -> tuple[list[GetCourseEntityDTO], dict[str, int]]:
        raw_items, source_counts = await self.client.fetch_entities_raw()
        entities: list[GetCourseEntityDTO] = []
        for item in raw_items:
            source = str(item.get("_gc_source") or "unknown")
            dto = self._build_entity(source, item)
            if dto is not None:
                entities.append(dto)
        return entities, source_counts

    @staticmethod
    def _detect_item_type(entity: GetCourseEntityDTO) -> str:
        source = (entity.entity_type or "").lower()
        raw_type = str(entity.raw.get("type") or entity.raw.get("entity_type") or "").lower()
        if "course" in source or "course" in raw_type or "курс" in raw_type:
            return "course"
        if "product" in source or "deal" in source or "product" in raw_type:
            return "product"
        return "product"

    @staticmethod
    def _detect_catalog_status(entity: GetCourseEntityDTO) -> str:
        raw_status = str(entity.raw.get("status") or "").strip().lower()
        inactive_markers = {"archived", "disabled", "hidden", "inactive", "closed"}
        if raw_status in inactive_markers:
            return "archived"

        for key in ("is_active", "active", "enabled", "published", "is_public"):
            value = entity.raw.get(key)
            if isinstance(value, bool):
                if not value:
                    return "archived"
        return "active"

    def split_entities(
        self,
        entities: list[GetCourseEntityDTO],
    ) -> tuple[list[GetCourseEntityDTO], list[GetCourseEntityDTO]]:
        dated: list[GetCourseEntityDTO] = []
        undated_catalog: list[GetCourseEntityDTO] = []
        for entity in entities:
            if entity.start_at is not None:
                dated.append(entity)
                continue
            entity_type = self._detect_item_type(entity)
            if entity_type in {"course", "product"}:
                undated_catalog.append(entity)
        return dated, undated_catalog

    def normalize_entity_to_event_fields(self, entity: GetCourseEntityDTO) -> dict[str, Any]:
        starts_at = entity.start_at
        status = "active"
        if starts_at and starts_at < datetime.now(tz=timezone.utc):
            status = "finished"

        description = entity.description or entity.title
        return {
            "title": entity.title,
            "description": description,
            "location": "Онлайн",
            "link_getcourse": entity.url,
            "price": entity.price,
            "status": status,
            "date": starts_at.date() if starts_at else None,
            "starts_at": starts_at,
            "external_source": "getcourse",
            "external_id": entity.external_id,
            "external_updated_at": entity.updated_at,
            "entity_type": entity.entity_type,
        }

    def normalize_entity_to_catalog_fields(self, entity: GetCourseEntityDTO) -> dict[str, Any]:
        return {
            "title": entity.title,
            "description": entity.description or entity.title,
            "price": entity.price,
            "currency": "RUB",
            "link_getcourse": entity.url,
            "item_type": self._detect_item_type(entity),
            "status": self._detect_catalog_status(entity),
            "external_source": "getcourse",
            "external_id": entity.external_id,
            "external_updated_at": entity.updated_at,
        }

    async def save_sync_result(
        self,
        *,
        fetched: int,
        imported_events: dict[str, int],
        imported_catalog: dict[str, int],
        source_counts: dict[str, int],
        error: str | None,
    ) -> None:
        state = await self._state()
        events_created = int(imported_events.get("created", 0) or 0)
        events_updated = int(imported_events.get("updated", 0) or 0)
        events_skipped = int(imported_events.get("skipped", 0) or 0)
        events_no_date = int(imported_events.get("no_date", 0) or 0)

        catalog_created = int(imported_catalog.get("created", 0) or 0)
        catalog_updated = int(imported_catalog.get("updated", 0) or 0)
        catalog_skipped = int(imported_catalog.get("skipped", 0) or 0)
        catalog_total = catalog_created + catalog_updated + catalog_skipped

        payload = {
            "courses": int(source_counts.get("courses", 0)),
            "products": int(source_counts.get("products", 0)),
            "events": int(source_counts.get("webinars", 0) + source_counts.get("events", 0)),
            "catalog_items": int(catalog_total),
            "fetched": int(fetched),
            "created": events_created,
            "updated": events_updated,
            "skipped": events_skipped,
            "no_date": events_no_date,
            "catalog_created": catalog_created,
            "catalog_updated": catalog_updated,
            "catalog_skipped": catalog_skipped,
            "sources": source_counts,
            "source": self.client.base_url,
        }

        state.payload_json = json.dumps(payload, ensure_ascii=False)
        state.last_sync_at = datetime.utcnow()
        state.last_error = error
        state.updated_at = datetime.utcnow()
        await self.db.flush()

    async def summary(self) -> dict[str, Any]:
        state = await self._state()
        payload: dict[str, Any] = {}
        if state.payload_json:
            try:
                raw = json.loads(state.payload_json)
                if isinstance(raw, dict):
                    payload = raw
            except Exception:
                payload = {}

        enabled = self.client.enabled
        status = "DISABLED"
        if enabled and state.last_error:
            status = "ERROR"
        elif enabled and state.last_sync_at:
            status = "OK"

        fetched = int(payload.get("fetched", 0) or 0)
        created = int(payload.get("created", 0) or 0)
        updated = int(payload.get("updated", 0) or 0)
        skipped = int(payload.get("skipped", 0) or 0)
        no_date = int(payload.get("no_date", 0) or 0)
        catalog_created = int(payload.get("catalog_created", 0) or 0)
        catalog_updated = int(payload.get("catalog_updated", 0) or 0)
        catalog_skipped = int(payload.get("catalog_skipped", 0) or 0)

        return {
            "enabled": enabled,
            "status": status,
            "lastSyncAt": state.last_sync_at.isoformat() if state.last_sync_at else None,
            "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
            "counts": {
                "courses": int(payload.get("courses", 0) or 0),
                "products": int(payload.get("products", 0) or 0),
                "events": int(payload.get("events", 0) or 0),
                "catalog_items": int(payload.get("catalog_items", 0) or 0),
                "fetched": fetched,
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "no_date": no_date,
            },
            "sourceUrl": self.client.base_url,
            "lastError": state.last_error,
            "ok": state.last_error is None,
            "fetched": fetched,
            "imported": {  # backwards compatibility: old clients read events as "imported"
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "no_date": no_date,
            },
            "importedEvents": {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "no_date": no_date,
            },
            "importedCatalog": {
                "created": catalog_created,
                "updated": catalog_updated,
                "skipped": catalog_skipped,
            },
        }
