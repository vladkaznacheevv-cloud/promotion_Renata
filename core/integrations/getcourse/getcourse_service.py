from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import unescape
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.models import GetCourseWebhookEvent, IntegrationState
from .getcourse_client import GetCourseClient
from .url_utils import normalize_getcourse_url

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
    url_source: str | None
    url_error: str | None
    price: float | None
    start_at: datetime | None
    updated_at: datetime | None
    raw: dict[str, Any]


@dataclass
class GetCourseService:
    db: AsyncSession

    def __post_init__(self) -> None:
        self.client = GetCourseClient()
        self.export_client = None

    @property
    def enabled(self) -> bool:
        return (os.getenv("GETCOURSE_ENABLED", "false").lower() == "true") and bool(self.client.base_url)

    @staticmethod
    def _is_export_runtime_enabled() -> bool:
        return (os.getenv("GETCOURSE_EXPORT_ENABLED", "false").strip().lower() == "true")

    def _get_export_client(self):
        if self.export_client is not None:
            return self.export_client
        if not self._is_export_runtime_enabled():
            return None
        # Lazy import keeps export pipeline out of default runtime path.
        from .getcourse_export_client import GetCourseExportClient

        self.export_client = GetCourseExportClient()
        return self.export_client

    @staticmethod
    def _resource_list(env_name: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            return fallback
        values = [part.strip().strip("/") for part in raw.split(",") if part.strip()]
        return tuple(values) if values else fallback

    async def fetch_export_payloads(
        self,
        *,
        sync_users: bool = True,
        sync_payments: bool = True,
        sync_catalog: bool = True,
    ) -> dict[str, Any]:
        export_client = self._get_export_client()
        if export_client is None:
            return {
                "users": [],
                "payments": [],
                "catalog": [],
                "counts": {},
                "errors": [],
                "unsupported_resources": [],
                "resource_statuses": {"users": [], "payments": [], "catalog": []},
                "busy_resources": [],
                "fatal_auth_error": False,
                "successful_resources": 0,
            }

        users_items: list[dict[str, Any]] = []
        payments_items: list[dict[str, Any]] = []
        catalog_items: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        errors: list[str] = []
        unsupported_resources: list[str] = []
        resource_statuses: dict[str, list[dict[str, Any]]] = {"users": [], "payments": [], "catalog": []}
        busy_resources: list[str] = []
        fatal_auth_error = False
        successful_resources = 0

        state = await self._state()
        last_sync_at = state.last_sync_at

        async def _fetch_one(group: str, resource: str) -> list[dict[str, Any]]:
            nonlocal fatal_auth_error, successful_resources
            result = await export_client.export_resource(resource, last_sync_at=last_sync_at)
            counts[resource] = int(result.fetched or 0)
            status = "ok"
            if result.error_kind == "unsupported":
                status = "unsupported"
                unsupported_resources.append(resource)
            elif result.error_kind == "busy":
                status = "busy"
                busy_resources.append(resource)
            elif result.error_kind == "auth_error":
                status = "auth_error"
            elif result.error:
                status = result.error_kind or "error"
            resource_statuses[group].append(
                {
                    "name": resource,
                    "status": status,
                    "http_status": result.status_code,
                    "fetched": int(result.fetched or 0),
                }
            )

            if result.error:
                if result.error_kind == "auth_error":
                    fatal_auth_error = True
                    errors.append(f"{resource}: auth_error")
                elif result.error_kind == "busy":
                    errors.append(f"{resource}: busy")
                elif result.error_kind != "unsupported":
                    errors.append(f"{resource}: {result.error_kind or 'request_error'}")
                return []
            successful_resources += 1
            return result.items

        if sync_users:
            for resource in self._resource_list("GETCOURSE_USERS_RESOURCES", ("users",)):
                items = await _fetch_one("users", resource)
                users_items.extend(items)

        if sync_payments:
            for resource in self._resource_list("GETCOURSE_PAYMENTS_RESOURCES", ("payments", "transactions")):
                items = await _fetch_one("payments", resource)
                payments_items.extend(items)

        if sync_catalog:
            for resource in self._resource_list("GETCOURSE_CATALOG_RESOURCES", ("deals", "offers", "products", "courses")):
                items = await _fetch_one("catalog", resource)
                catalog_items.extend(items)

        return {
            "users": users_items,
            "payments": payments_items,
            "catalog": catalog_items,
            "counts": counts,
            "errors": errors,
            "unsupported_resources": unsupported_resources,
            "resource_statuses": resource_statuses,
            "busy_resources": busy_resources,
            "fatal_auth_error": fatal_auth_error,
            "successful_resources": successful_resources,
        }

    async def ping_export(self) -> dict[str, Any]:
        key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        base_url = self.client.base_url
        account_name = (os.getenv("GETCOURSE_ACCOUNT") or "").strip() or (urlparse(base_url).hostname or "").split(".")[0]
        ping_result = {
            "ok": bool(base_url),
            "resource": "config",
            "status_code": 200,
            "error_kind": None,
            "error_code": None,
            "error_message": None,
        }
        return {
            "enabled": self.enabled,
            "base_url": base_url,
            "account_name": account_name or None,
            "api_key_present": bool(key),
            "api_key_len": len(key),
            "probe": ping_result,
        }

    async def diagnose_resources(self) -> dict[str, Any]:
        key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        configured_resources: list[str] = []
        for group_resources in (
            self._resource_list("GETCOURSE_USERS_RESOURCES", ("users",)),
            self._resource_list("GETCOURSE_PAYMENTS_RESOURCES", ("payments",)),
            self._resource_list("GETCOURSE_CATALOG_RESOURCES", ("deals",)),
        ):
            configured_resources.extend(group_resources)

        resource_statuses = {
            resource: {"ok": bool(self.enabled), "status_code": 200 if self.enabled else None, "error_kind": None}
            for resource in configured_resources
        }
        successful_resources = list(resource_statuses.keys()) if self.enabled else []
        unsupported_resources: list[str] = []
        fatal_auth_error = False

        return {
            "enabled": self.enabled,
            "has_key": bool(key),
            "base_url": self.client.base_url,
            "resourceStatuses": resource_statuses,
            "unsupportedResources": unsupported_resources,
            "fatalAuthError": fatal_auth_error,
            "successfulResources": successful_resources,
        }

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
    def _first_non_empty(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", []):
                return value
        return None

    async def store_webhook_event(self, payload: dict[str, Any]) -> GetCourseWebhookEvent:
        state = await self._state()
        canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        event_id = str(
            self._first_non_empty(payload, ("event_id", "id", "webhook_event_id", "request_id")) or ""
        ).strip()
        dedupe_key = f"id:{event_id}" if event_id else f"hash:{payload_hash}"

        existing_row = await self.db.execute(
            select(GetCourseWebhookEvent).where(GetCourseWebhookEvent.dedupe_key == dedupe_key).limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        if existing is not None:
            state.last_sync_at = datetime.utcnow()
            state.updated_at = datetime.utcnow()
            await self.db.flush()
            return existing

        event_type = str(
            self._first_non_empty(payload, ("event_type", "type", "event", "action")) or "unknown"
        ).strip() or "unknown"
        amount_value = self._first_non_empty(payload, ("amount", "sum", "price"))
        amount: Decimal | None = None
        if amount_value not in (None, ""):
            try:
                amount = Decimal(str(amount_value).replace(",", "."))
            except Exception:
                amount = None

        event = GetCourseWebhookEvent(
            event_id=event_id or None,
            payload_hash=payload_hash,
            dedupe_key=dedupe_key,
            event_type=event_type[:100],
            user_email=(str(self._first_non_empty(payload, ("user_email", "email")) or "").strip() or None),
            user_id=(str(self._first_non_empty(payload, ("user_id", "contact_id", "client_id")) or "").strip() or None),
            deal_id=(str(self._first_non_empty(payload, ("deal_id", "order_id", "payment_id")) or "").strip() or None),
            deal_number=(str(self._first_non_empty(payload, ("deal_number", "order_number", "number")) or "").strip() or None),
            amount=amount,
            currency=(str(self._first_non_empty(payload, ("currency",)) or "").strip() or None),
            status=(str(self._first_non_empty(payload, ("status", "payment_status")) or "").strip() or None),
            raw_payload=canonical_payload,
        )
        self.db.add(event)
        state.last_sync_at = datetime.utcnow()
        state.updated_at = datetime.utcnow()
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            row = await self.db.execute(
                select(GetCourseWebhookEvent).where(GetCourseWebhookEvent.dedupe_key == dedupe_key).limit(1)
            )
            existing = row.scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return event

    async def list_webhook_events(self, limit: int = 50) -> list[GetCourseWebhookEvent]:
        safe_limit = max(1, min(int(limit or 50), 100))
        row = await self.db.execute(
            select(GetCourseWebhookEvent)
            .order_by(GetCourseWebhookEvent.received_at.desc())
            .limit(safe_limit)
        )
        return list(row.scalars())

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

    def _pick_entity_url(self, raw: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        fields = ("url", "link", "public_url", "landing_url", "href")
        first_error: str | None = None
        first_source: str | None = None
        for field_name in fields:
            if field_name not in raw or raw.get(field_name) in (None, ""):
                continue
            normalized, reason = normalize_getcourse_url(
                raw.get(field_name),
                base_url=self.client.base_url,
            )
            if normalized:
                return normalized, field_name, None
            if first_error is None:
                first_error = reason
                first_source = field_name
            logger.warning(
                "GetCourse URL rejected: source_field=%s reason=%s value=%r",
                field_name,
                reason,
                raw.get(field_name),
            )
        return None, first_source, first_error

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
        link, url_source, url_error = self._pick_entity_url(raw)
        price = self._to_price(self._extract_value(raw, ("price", "amount", "sum", "cost", "offer_price")))
        start_at = self._to_datetime(self._extract_value(raw, ("start_at", "starts_at", "date_start", "start_date", "webinar_date", "date")))
        updated_at = self._to_datetime(self._extract_value(raw, ("updated_at", "modified_at", "updated", "changed_at")))

        return GetCourseEntityDTO(
            external_id=external_id,
            entity_type=source,
            title=title,
            description=description,
            url=link,
            url_source=url_source,
            url_error=url_error,
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
            "link_getcourse_source": entity.url_source,
            "url_error": entity.url_error,
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
            "link_getcourse_source": entity.url_source,
            "url_error": entity.url_error,
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
        unsupported_resources: list[str] | None = None,
        resource_statuses: dict[str, list[dict[str, Any]]] | None = None,
        imported_users: dict[str, int] | None = None,
        imported_payments: dict[str, int] | None = None,
        resource_sync_at: dict[str, str | None] | None = None,
    ) -> None:
        state = await self._state()
        events_created = int(imported_events.get("created", 0) or 0)
        events_updated = int(imported_events.get("updated", 0) or 0)
        events_skipped = int(imported_events.get("skipped", 0) or 0)
        events_no_date = int(imported_events.get("no_date", 0) or 0)
        events_bad_url = int(imported_events.get("bad_url", 0) or 0)

        catalog_created = int(imported_catalog.get("created", 0) or 0)
        catalog_updated = int(imported_catalog.get("updated", 0) or 0)
        catalog_skipped = int(imported_catalog.get("skipped", 0) or 0)
        catalog_bad_url = int(imported_catalog.get("bad_url", 0) or 0)
        catalog_total = catalog_created + catalog_updated + catalog_skipped
        bad_url = events_bad_url + catalog_bad_url

        imported_users = imported_users or {"created": 0, "updated": 0, "skipped": 0}
        imported_payments = imported_payments or {"created": 0, "updated": 0, "skipped": 0}
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
            "bad_url": bad_url,
            "catalog_created": catalog_created,
            "catalog_updated": catalog_updated,
            "catalog_skipped": catalog_skipped,
            "catalog_bad_url": catalog_bad_url,
            "users_created": int(imported_users.get("created", 0) or 0),
            "users_updated": int(imported_users.get("updated", 0) or 0),
            "users_skipped": int(imported_users.get("skipped", 0) or 0),
            "payments_created": int(imported_payments.get("created", 0) or 0),
            "payments_updated": int(imported_payments.get("updated", 0) or 0),
            "payments_skipped": int(imported_payments.get("skipped", 0) or 0),
            "sources": source_counts,
            "unsupported_resources": unsupported_resources or [],
            "resource_statuses": resource_statuses or {"users": [], "payments": [], "catalog": []},
            "resource_sync_at": resource_sync_at or {},
            "source": self.client.base_url,
        }

        state.payload_json = json.dumps(payload, ensure_ascii=False)
        state.last_sync_at = datetime.utcnow()
        state.last_error = error
        state.updated_at = datetime.utcnow()
        await self.db.flush()

    async def summary(self) -> dict[str, Any]:
        state = await self._state()
        now = datetime.now(tz=timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        last_event_row = await self.db.execute(
            select(GetCourseWebhookEvent.received_at)
            .order_by(GetCourseWebhookEvent.received_at.desc())
            .limit(1)
        )
        last_event_at = last_event_row.scalar_one_or_none()

        events_last_24h_row = await self.db.execute(
            select(func.count(GetCourseWebhookEvent.id)).where(GetCourseWebhookEvent.received_at >= day_ago)
        )
        events_last_24h = int(events_last_24h_row.scalar_one() or 0)

        events_last_7d_row = await self.db.execute(
            select(func.count(GetCourseWebhookEvent.id)).where(GetCourseWebhookEvent.received_at >= week_ago)
        )
        events_last_7d = int(events_last_7d_row.scalar_one() or 0)

        key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        base_url = self.client.base_url
        enabled = bool((os.getenv("GETCOURSE_ENABLED", "false").lower() == "true") and base_url)
        status = "OK" if enabled else "DISABLED"
        if state.last_error:
            status = "ERROR"

        return {
            "enabled": enabled,
            "has_key": bool(key),
            "base_url": base_url,
            "status": status,
            "sourceUrl": base_url,
            "last_event_at": last_event_at.isoformat() if last_event_at else None,
            "events_last_24h": events_last_24h,
            "events_last_7d": events_last_7d,
            "lastError": state.last_error,
            "last_error": state.last_error,
            "ok": state.last_error is None,
            "counts": {
                "courses": 0,
                "products": 0,
                "events": events_last_7d,
                "catalog_items": 0,
                "users": 0,
                "payments": 0,
                "fetched": events_last_24h,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "no_date": 0,
                "bad_url": 0,
            },
            "lastSyncAt": state.last_sync_at.isoformat() if state.last_sync_at else None,
            "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
            "unsupportedResources": [],
            "fetched": events_last_24h,
            "imported": {"created": 0, "updated": 0, "skipped": 0, "no_date": 0, "bad_url": 0},
            "importedEvents": {"created": 0, "updated": 0, "skipped": 0, "no_date": 0, "bad_url": 0},
            "importedCatalog": {"created": 0, "updated": 0, "skipped": 0, "bad_url": 0},
            "importedUsers": {"created": 0, "updated": 0, "skipped": 0},
            "importedPayments": {"created": 0, "updated": 0, "skipped": 0},
            "syncAtByResource": {"users": None, "payments": None, "catalog": None},
        }
