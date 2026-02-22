from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type, datetime, time, timezone, timedelta
from decimal import Decimal
import json
import logging
import os
from uuid import uuid4
from typing import Any

import httpx
from sqlalchemy import String, and_, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.schemas import ClientCreate, ClientUpdate, EventCreate, EventUpdate
from core.crm.models import CRMUserActivity, ChannelInvite, UserSubscription
from core.crm.activity_service import ActivityService
from core.catalog.models import CatalogItem
from core.events.models import Event, UserEvent
from core.integrations.getcourse import GetCourseService
from core.integrations.getcourse.url_utils import normalize_getcourse_url
from core.payments.models import Payment
from core.users.models import User


STATUS_TO_DB = {
    "\u041d\u043e\u0432\u044b\u0439": User.STATUS_NEW,
    "\u0412 \u0440\u0430\u0431\u043e\u0442\u0435": User.STATUS_IN_WORK,
    "\u041a\u043b\u0438\u0435\u043d\u0442": User.STATUS_CLIENT,
    "VIP \u041a\u043b\u0438\u0435\u043d\u0442": User.STATUS_VIP,
}

DB_TO_STATUS = {
    User.STATUS_NEW: "\u041d\u043e\u0432\u044b\u0439",
    User.STATUS_IN_WORK: "\u0412 \u0440\u0430\u0431\u043e\u0442\u0435",
    User.STATUS_CLIENT: "\u041a\u043b\u0438\u0435\u043d\u0442",
    User.STATUS_VIP: "VIP \u041a\u043b\u0438\u0435\u043d\u0442",
}


logger = logging.getLogger(__name__)

EVENT_SCHEDULE_ONE_TIME = "one_time"
EVENT_SCHEDULE_RECURRING = "recurring"
EVENT_SCHEDULE_ROLLING = "rolling"
EVENT_SCHEDULE_CHOICES = {
    EVENT_SCHEDULE_ONE_TIME,
    EVENT_SCHEDULE_RECURRING,
    EVENT_SCHEDULE_ROLLING,
}
DEFAULT_RECURRING_RULE = {"freq": "MONTHLY", "bysetpos": [2, 4], "byweekday": "TU"}
DEFAULT_RECURRING_START_TIME = time(17, 0)
DEFAULT_RECURRING_END_TIME = time(21, 0)
DEFAULT_EVENT_HOSTS = (
    "Диана Даниелян — клинический психолог, гештальттерапевт\n"
    "Елена Анищенко — клинический психолог, супервизор, гештальттерапевт"
)
DEFAULT_DURATION_HINT = "Длительность игры 1–4 часа, в зависимости от количества игроков."
DEFAULT_BOOKING_HINT = "Запись по запросу в удобное время и дату."


class GetCourseSyncCooldownError(Exception):
    def __init__(self, *, next_allowed_at: datetime, cooldown_minutes: int) -> None:
        self.next_allowed_at = next_allowed_at
        self.cooldown_minutes = cooldown_minutes
        super().__init__("Sync cooldown active")


class GetCourseSyncAlreadyRunningError(Exception):
    pass


class CRMClientTelegramUnavailableError(Exception):
    pass


class CRMClientTelegramSendError(Exception):
    pass


@dataclass
class CRMService:
    db: AsyncSession
    _payments_event_id_exists: bool | None = field(default=None, init=False, repr=False)

    @staticmethod
    def normalize_stage(stage: str | None) -> str:
        if stage in User.CRM_STAGE_CHOICES:
            return stage
        return User.CRM_STAGE_NEW

    @classmethod
    def stage_after_message(cls, current_stage: str | None) -> str:
        stage = cls.normalize_stage(current_stage)
        if stage == User.CRM_STAGE_NEW:
            return User.CRM_STAGE_ENGAGED
        return stage

    @classmethod
    def stage_after_contacts(cls, current_stage: str | None) -> str:
        _ = cls.normalize_stage(current_stage)
        return User.CRM_STAGE_READY_TO_PAY

    @classmethod
    def stage_after_payment_paid(cls, current_stage: str | None) -> str:
        _ = cls.normalize_stage(current_stage)
        return User.CRM_STAGE_PAID

    @staticmethod
    def _normalize_schedule_type(value: str | None) -> str:
        normalized = (value or "").strip().lower()
        if normalized in EVENT_SCHEDULE_CHOICES:
            return normalized
        return EVENT_SCHEDULE_ONE_TIME

    @staticmethod
    def _normalize_text_field(value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None

    @staticmethod
    def _normalize_int_field(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_hhmm(value: Any) -> time | None:
        if value is None or value == "":
            return None
        if isinstance(value, time):
            return value.replace(second=0, microsecond=0)
        text_value = str(value).strip()
        if not text_value:
            return None
        try:
            parsed = datetime.strptime(text_value[:5], "%H:%M").time()
            return parsed.replace(second=0, microsecond=0)
        except ValueError:
            return None

    @staticmethod
    def _time_to_hhmm(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, time):
            return value.strftime("%H:%M")
        text_value = str(value).strip()
        if not text_value:
            return None
        return text_value[:5]

    @staticmethod
    def _normalize_recurring_rule(value: Any) -> dict[str, Any] | None:
        if value in (None, ""):
            return None
        rule: dict[str, Any] | None = None
        if isinstance(value, dict):
            rule = dict(value)
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                rule = dict(parsed)
        if not rule:
            return None

        weekday = str(rule.get("byweekday") or "TU").upper()
        if weekday not in {"MO", "TU", "WE", "TH", "FR", "SA", "SU"}:
            weekday = "TU"

        positions_raw = rule.get("bysetpos", [2, 4])
        if isinstance(positions_raw, list):
            positions = []
            for item in positions_raw:
                try:
                    num = int(item)
                except (TypeError, ValueError):
                    continue
                if 1 <= num <= 5 and num not in positions:
                    positions.append(num)
        else:
            positions = []
        if not positions:
            positions = [2, 4]
        positions.sort()

        freq = str(rule.get("freq") or "MONTHLY").upper()
        if freq != "MONTHLY":
            freq = "MONTHLY"

        return {"freq": freq, "bysetpos": positions, "byweekday": weekday}

    @staticmethod
    def _serialize_recurring_rule(rule: dict[str, Any] | None) -> str | None:
        if not rule:
            return None
        return json.dumps(rule, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _normalize_occurrence_dates(value: Any) -> list[date_type] | None:
        if value in (None, ""):
            return None

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, list):
                return None
            items = parsed
        elif isinstance(value, list):
            items = value
        else:
            return None

        result: list[date_type] = []
        for item in items:
            parsed_date: date_type | None = None
            if isinstance(item, datetime):
                parsed_date = item.date()
            elif isinstance(item, date_type):
                parsed_date = item
            else:
                text_value = str(item or "").strip()
                if text_value:
                    try:
                        parsed_date = datetime.fromisoformat(text_value[:10]).date()
                    except ValueError:
                        parsed_date = None
            if parsed_date and parsed_date not in result:
                result.append(parsed_date)
        result.sort()
        return result or None

    @staticmethod
    def _serialize_occurrence_dates(values: list[date_type] | None) -> str | None:
        if not values:
            return None
        return json.dumps([value.isoformat() for value in values], ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _normalize_pricing_options(value: Any) -> list[dict[str, Any]] | None:
        if value in (None, ""):
            return None

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, list):
                return None
            items = parsed
        elif isinstance(value, list):
            items = value
        else:
            return None

        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            try:
                price_rub = int(item.get("price_rub"))
            except (TypeError, ValueError):
                continue
            if price_rub < 0:
                continue
            note_raw = item.get("note")
            note = str(note_raw).strip() if note_raw is not None else None
            result.append({"label": label, "price_rub": price_rub, "note": note or None})
        return result or None

    @staticmethod
    def _serialize_pricing_options(values: list[dict[str, Any]] | None) -> str | None:
        if not values:
            return None
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _to_start_of_day(value: date_type | datetime | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(hour=0, minute=0, second=0, microsecond=0)
        return datetime.combine(value, time.min)

    @staticmethod
    def _format_date_short(value: date_type | datetime | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%d.%m")
        return value.strftime("%d.%m")

    @staticmethod
    def _format_date_full(value: date_type | datetime | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        return value.strftime("%d.%m.%Y")

    @classmethod
    def _time_range_text(cls, start_time_value: Any, end_time_value: Any) -> str | None:
        start_hhmm = cls._time_to_hhmm(start_time_value)
        end_hhmm = cls._time_to_hhmm(end_time_value)
        if start_hhmm and end_hhmm:
            return f"{start_hhmm}–{end_hhmm}"
        return start_hhmm or end_hhmm

    @staticmethod
    def _recurring_weekday_ru(code: str) -> str:
        mapping = {
            "MO": "понедельник",
            "TU": "вторник",
            "WE": "среда",
            "TH": "четверг",
            "FR": "пятница",
            "SA": "суббота",
            "SU": "воскресенье",
        }
        return mapping.get((code or "").upper(), "вторник")

    @classmethod
    def _recurring_schedule_text(cls, recurring_rule: dict[str, Any] | None, start_time_value: Any, end_time_value: Any) -> str:
        rule = recurring_rule or DEFAULT_RECURRING_RULE
        positions_raw = rule.get("bysetpos") or [2, 4]
        positions: list[int] = []
        for item in positions_raw if isinstance(positions_raw, list) else [2, 4]:
            try:
                num = int(item)
            except (TypeError, ValueError):
                continue
            if 1 <= num <= 5:
                positions.append(num)
        if not positions:
            positions = [2, 4]
        weekday = cls._recurring_weekday_ru(str(rule.get("byweekday") or "TU"))
        pos_text = " и ".join(f"{pos}-й" for pos in positions)
        start_hhmm = cls._time_to_hhmm(start_time_value) or DEFAULT_RECURRING_START_TIME.strftime("%H:%M")
        end_hhmm = cls._time_to_hhmm(end_time_value) or DEFAULT_RECURRING_END_TIME.strftime("%H:%M")
        return f"{pos_text} {weekday}, {start_hhmm}–{end_hhmm}"

    @classmethod
    def _event_schedule_text(
        cls,
        event: Event,
        recurring_rule: dict[str, Any] | None = None,
        occurrence_dates: list[date_type] | None = None,
    ) -> str | None:
        schedule_type = cls._normalize_schedule_type(getattr(event, "schedule_type", None))
        if schedule_type == EVENT_SCHEDULE_ROLLING:
            return "\u0411\u0435\u0437 \u0434\u0430\u0442\u044b / \u043f\u043e \u0437\u0430\u043f\u0440\u043e\u0441\u0443"
        if schedule_type == EVENT_SCHEDULE_RECURRING:
            if occurrence_dates:
                dates_text = ", ".join(
                    part for part in (cls._format_date_short(item) for item in occurrence_dates) if part
                )
                parts: list[str] = []
                if dates_text:
                    parts.append(f"\u0414\u0430\u0442\u044b: {dates_text}")
                time_text = cls._time_range_text(event.start_time, event.end_time)
                if time_text:
                    parts.append(time_text)
                return "; ".join(parts) if parts else None

            rule_text = cls._recurring_schedule_text(recurring_rule, event.start_time, event.end_time)
            start_text = cls._format_date_full(getattr(event, "start_date", None))
            if start_text:
                return f"\u0421\u0442\u0430\u0440\u0442 {start_text}; {rule_text}"
            return rule_text
        return None

    async def _payments_has_event_id(self) -> bool:
        if self._payments_event_id_exists is not None:
            return self._payments_event_id_exists

        res = await self.db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'payments'
                  AND column_name = 'event_id'
                LIMIT 1
                """
            )
        )
        self._payments_event_id_exists = res.scalar_one_or_none() is not None
        return self._payments_event_id_exists

    async def list_clients(
        self,
        limit: int = 10,
        stage: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        query = select(User).where(User.status != User.STATUS_ARCHIVED)

        if stage:
            query = query.where(User.crm_stage == self.normalize_stage(stage))

        search_text = (search or "").strip()
        if search_text:
            pattern = f"%{search_text}%"
            query = query.where(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.phone.ilike(pattern),
                    cast(User.tg_id, String).ilike(pattern),
                )
            )

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))

        result = await self.db.execute(
            query.order_by(User.created_at.desc()).limit(limit)
        )
        users = result.scalars().all()
        items = await self._build_client_items(users)

        return {"items": items, "total": int(total or 0)}

    async def list_events(self, limit: int = 10, status: str | None = None) -> dict[str, Any]:
        query = select(Event)
        if status == "active":
            query = query.where(Event.is_active.is_(True))
        elif status == "finished":
            query = query.where(Event.is_active.is_(False))

        total_query = select(func.count(Event.id))
        if status == "active":
            total_query = total_query.where(Event.is_active.is_(True))
        elif status == "finished":
            total_query = total_query.where(Event.is_active.is_(False))

        total = await self.db.scalar(total_query)

        result = await self.db.execute(query.order_by(Event.created_at.desc()).limit(limit))
        events = result.scalars().all()

        event_ids = [event.id for event in events]
        attendees_map: dict[int, int] = {}
        if event_ids:
            rows = await self.db.execute(
                select(UserEvent.event_id, func.count(UserEvent.id))
                .where(UserEvent.event_id.in_(event_ids))
                .where(UserEvent.status != "cancelled")
                .group_by(UserEvent.event_id)
            )
            attendees_map = {row[0]: int(row[1]) for row in rows}

        revenue_map: dict[int, int] = {}
        if event_ids and await self._payments_has_event_id():
            rows = await self.db.execute(
                select(Payment.event_id, func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.event_id.in_(event_ids))
                .where(Payment.status == "paid")
                .group_by(Payment.event_id)
            )
            revenue_map = {row[0]: int(row[1] or 0) for row in rows}

        items = [
            self._event_out(
                event,
                attendees_map.get(event.id, 0),
                revenue=revenue_map.get(event.id, 0),
            )
            for event in events
        ]
        return {"items": items, "total": int(total or 0)}

    async def list_active_events(self, limit: int = 50) -> dict[str, Any]:
        query = select(Event).where(Event.is_active.is_(True))
        total = await self.db.scalar(select(func.count(Event.id)).where(Event.is_active.is_(True)))
        result = await self.db.execute(
            query.order_by(Event.starts_at.asc().nulls_last()).limit(limit)
        )
        events = result.scalars().all()
        items = [self._event_summary(event) for event in events]
        return {"items": items, "total": int(total or 0)}

    async def list_catalog(
        self,
        *,
        item_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(CatalogItem)

        normalized_type = (item_type or "").strip().lower()
        if normalized_type in {"course", "product"}:
            query = query.where(CatalogItem.item_type == normalized_type)

        search_text = (search or "").strip()
        if search_text:
            pattern = f"%{search_text}%"
            query = query.where(
                or_(
                    CatalogItem.title.ilike(pattern),
                    CatalogItem.description.ilike(pattern),
                )
            )

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.db.execute(
            query.order_by(CatalogItem.updated_at.desc()).limit(limit).offset(offset)
        )
        items = [self._catalog_out(item) for item in rows.scalars().all()]
        return {"items": items, "total": int(total or 0)}

    async def get_catalog_item(self, item_id: int) -> dict[str, Any] | None:
        row = await self.db.execute(select(CatalogItem).where(CatalogItem.id == item_id))
        item = row.scalar_one_or_none()
        if item is None:
            return None
        return self._catalog_out(item)

    async def get_ai_stats(self) -> dict[str, Any]:
        active_users = await self.db.scalar(select(func.count(User.id)))
        return {
            "totalResponses": 0,
            "activeUsers": int(active_users or 0),
            "avgRating": 0.0,
            "responseTime": 0.0,
            "topQuestions": [],
        }

    async def create_client(self, data: ClientCreate) -> dict[str, Any]:
        payload = data.model_dump()
        tg_id = payload.get("tg_id") or await self._generate_tg_id()

        name = (payload.get("name") or "").strip()
        first_name, last_name = self._split_name(name)

        username = self._normalize_username(payload.get("telegram"))
        status_label = payload.get("status") or "\u041d\u043e\u0432\u044b\u0439"
        status_code = STATUS_TO_DB.get(status_label, User.STATUS_NEW)
        stage = payload.get("stage")
        if not stage and (payload.get("phone") or payload.get("email")):
            stage = User.CRM_STAGE_READY_TO_PAY
        now = datetime.utcnow()

        user = User(
            tg_id=tg_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            phone=payload.get("phone"),
            email=payload.get("email"),
            status=status_code,
            source="crm",
            is_vip=status_code == User.STATUS_VIP,
            interested_event_id=payload.get("interested_event_id"),
            crm_stage=self.normalize_stage(stage),
            last_activity_at=now,
        )
        self.db.add(user)
        await self.db.flush()

        activity_service = ActivityService(self.db)
        activity = await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )

        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(
                select(Event.title).where(Event.id == user.interested_event_id)
            )
            interested_title = row.scalar_one_or_none()

        return self._client_out(
            user,
            revenue=0,
            interested=interested_title,
            activity=(activity.ai_chats or 0, activity.last_activity_at),
        )

    async def update_client(self, client_id: int, data: ClientUpdate) -> dict[str, Any] | None:
        user = await self._get_user(client_id)
        if user is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        changed = False

        if "name" in payload:
            first_name, last_name = self._split_name(payload.get("name") or "")
            user.first_name = first_name
            user.last_name = last_name
            changed = True
        if "telegram" in payload:
            user.username = self._normalize_username(payload.get("telegram"))
            changed = True
        if "status" in payload:
            status_label = payload.get("status")
            status_code = STATUS_TO_DB.get(status_label, User.STATUS_NEW)
            user.status = status_code
            user.is_vip = status_code == User.STATUS_VIP
            changed = True
        if "interested_event_id" in payload:
            user.interested_event_id = payload.get("interested_event_id")
            changed = True

        contacts_updated = False
        if "phone" in payload:
            user.phone = payload.get("phone") or None
            contacts_updated = True
            changed = True
        if "email" in payload:
            user.email = payload.get("email") or None
            contacts_updated = True
            changed = True

        if "stage" in payload and payload.get("stage"):
            user.crm_stage = self.normalize_stage(payload.get("stage"))
            changed = True
        elif contacts_updated and (user.phone or user.email):
            user.crm_stage = self.stage_after_contacts(user.crm_stage)
            changed = True
        elif not user.crm_stage:
            user.crm_stage = User.CRM_STAGE_NEW
            changed = True

        now = datetime.utcnow()
        if changed:
            user.last_activity_at = now

        await self.db.flush()

        activity_service = ActivityService(self.db)
        activity = await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )

        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(
                select(Event.title).where(Event.id == user.interested_event_id)
            )
            interested_title = row.scalar_one_or_none()

        revenue = await self._get_revenue(user.id)
        return self._client_out(
            user,
            revenue=revenue,
            interested=interested_title,
            activity=(activity.ai_chats or 0, activity.last_activity_at),
        )

    async def update_client_contacts(
        self,
        tg_id: int,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any] | None:
        user = await self._get_user_by_tg_id(tg_id)
        if user is None:
            return None

        if phone is not None:
            user.phone = phone or None
        if email is not None:
            user.email = email or None

        now = datetime.utcnow()
        user.crm_stage = self.stage_after_contacts(user.crm_stage)
        user.last_activity_at = now
        await self.db.flush()

        activity_service = ActivityService(self.db)
        activity = await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )

        revenue = await self._get_revenue(user.id)
        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(select(Event.title).where(Event.id == user.interested_event_id))
            interested_title = row.scalar_one_or_none()

        return self._client_out(
            user,
            revenue=revenue,
            interested=interested_title,
            activity=(activity.ai_chats or 0, activity.last_activity_at),
        )

    async def set_client_stage(self, user_id: int, stage: str) -> dict[str, Any] | None:
        user = await self._get_user(user_id)
        if user is None:
            return None

        now = datetime.utcnow()
        user.crm_stage = self.normalize_stage(stage)
        user.last_activity_at = now
        await self.db.flush()

        activity_service = ActivityService(self.db)
        activity = await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )

        revenue = await self._get_revenue(user.id)
        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(select(Event.title).where(Event.id == user.interested_event_id))
            interested_title = row.scalar_one_or_none()

        return self._client_out(
            user,
            revenue=revenue,
            interested=interested_title,
            activity=(activity.ai_chats or 0, activity.last_activity_at),
        )

    async def set_client_stage_by_tg_id(self, tg_id: int, stage: str) -> User | None:
        user = await self._get_user_by_tg_id(tg_id)
        if user is None:
            return None

        now = datetime.utcnow()
        user.crm_stage = self.normalize_stage(stage)
        user.last_activity_at = now
        activity_service = ActivityService(self.db)
        await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )
        await self.db.flush()
        return user

    async def touch_client_activity_by_tg_id(
        self,
        tg_id: int,
        ai_increment: int = 0,
    ) -> User | None:
        user = await self._get_user_by_tg_id(tg_id)
        if user is None:
            return None

        now = datetime.utcnow()
        user.crm_stage = self.stage_after_message(user.crm_stage)
        user.last_activity_at = now

        activity_service = ActivityService(self.db)
        await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=max(ai_increment, 0),
        )
        await self.db.flush()
        return user

    async def delete_client(self, client_id: int) -> bool:
        user = await self._get_user(client_id)
        if user is None:
            return False
        try:
            async with self.db.begin_nested():
                await self.db.delete(user)
                await self.db.flush()
            return True
        except IntegrityError:
            logger.info("Client hard-delete failed, applying soft-delete fallback: client_id=%s", client_id)

        user = await self._get_user(client_id)
        if user is None:
            return True

        now = datetime.utcnow()
        user.first_name = "deleted"
        user.last_name = str(user.id)
        user.username = None
        user.phone = None
        user.email = None
        user.is_vip = False
        user.status = User.STATUS_ARCHIVED
        user.crm_stage = User.CRM_STAGE_INACTIVE
        user.last_activity_at = now
        await self.db.flush()
        return True

    async def request_client_contacts_via_bot(self, client_id: int) -> dict[str, Any] | None:
        user = await self._get_user(client_id)
        if user is None:
            return None
        if not user.tg_id:
            raise CRMClientTelegramUnavailableError("Client has no Telegram ID")

        bot_token = (os.getenv("BOT_TOKEN") or "").strip()
        if not bot_token:
            raise CRMClientTelegramSendError("BOT_TOKEN not configured")

        text_message = (
            "С Вами хочет связаться ассистент Ренаты. "
            "Оставьте, пожалуйста, номер телефона и почту."
        )
        reply_markup = {
            "keyboard": [
                [{"text": "📱 Отправить номер", "request_contact": True}],
                [{"text": "В меню"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": int(user.tg_id),
                        "text": text_message,
                        "reply_markup": reply_markup,
                    },
                )
            payload = response.json()
        except Exception as exc:
            logger.warning(
                "Failed to send CRM contact request via Telegram: client_id=%s tg_id=%s error=%s",
                client_id,
                user.tg_id,
                exc,
            )
            raise CRMClientTelegramSendError("Failed to send Telegram message") from exc

        if response.status_code >= 400 or not payload.get("ok"):
            logger.warning(
                "Telegram sendMessage rejected CRM contact request: client_id=%s tg_id=%s status=%s",
                client_id,
                user.tg_id,
                response.status_code,
            )
            raise CRMClientTelegramSendError("Failed to send Telegram message")

        return {"ok": True}

    async def create_event(self, data: EventCreate) -> dict[str, Any]:
        payload = data.model_dump()
        status = payload.get("status") or "active"
        is_active = status == "active"
        schedule_type = self._normalize_schedule_type(payload.get("schedule_type"))

        starts_at = None
        start_date_value = self._to_start_of_day(payload.get("start_date"))
        if payload.get("date"):
            starts_at = datetime.combine(payload["date"], time.min)
            if schedule_type == EVENT_SCHEDULE_ONE_TIME:
                start_date_value = starts_at

        occurrence_dates = self._normalize_occurrence_dates(payload.get("occurrence_dates"))
        pricing_options = self._normalize_pricing_options(payload.get("pricing_options"))

        price = payload.get("price")
        if pricing_options:
            price = pricing_options[0]["price_rub"]
        if price is not None:
            price = Decimal(str(price))

        start_time_value = self._parse_hhmm(payload.get("start_time"))
        end_time_value = self._parse_hhmm(payload.get("end_time"))
        recurring_rule = self._normalize_recurring_rule(payload.get("recurring_rule"))
        if schedule_type == EVENT_SCHEDULE_RECURRING:
            starts_at = None
            if not occurrence_dates:
                recurring_rule = recurring_rule or dict(DEFAULT_RECURRING_RULE)
            start_time_value = start_time_value or DEFAULT_RECURRING_START_TIME
            end_time_value = end_time_value or DEFAULT_RECURRING_END_TIME
        elif schedule_type == EVENT_SCHEDULE_ROLLING:
            starts_at = None
            start_date_value = None
            start_time_value = None
            end_time_value = None
            recurring_rule = None
            occurrence_dates = None
        else:
            if starts_at is None and payload.get("date"):
                starts_at = datetime.combine(payload["date"], time.min)
            if starts_at is not None:
                start_date_value = starts_at
            start_time_value = None
            end_time_value = None
            recurring_rule = None
            occurrence_dates = None

        hosts = self._normalize_text_field(payload.get("hosts")) or DEFAULT_EVENT_HOSTS
        duration_hint = self._normalize_text_field(payload.get("duration_hint")) or DEFAULT_DURATION_HINT
        booking_hint = self._normalize_text_field(payload.get("booking_hint")) or DEFAULT_BOOKING_HINT
        price_individual_rub = self._normalize_int_field(payload.get("price_individual_rub"))
        price_group_rub = self._normalize_int_field(payload.get("price_group_rub"))

        event = Event(
            title=payload.get("title"),
            description=payload.get("description"),
            location=payload.get("location"),
            schedule_type=schedule_type,
            start_date=start_date_value,
            start_time=start_time_value,
            end_time=end_time_value,
            recurring_rule=self._serialize_recurring_rule(recurring_rule),
            occurrence_dates=self._serialize_occurrence_dates(occurrence_dates),
            pricing_options=self._serialize_pricing_options(pricing_options),
            hosts=hosts,
            price_individual_rub=price_individual_rub,
            price_group_rub=price_group_rub,
            duration_hint=duration_hint,
            booking_hint=booking_hint,
            link_getcourse=None,
            starts_at=starts_at,
            price=price,
            is_active=is_active,
        )
        self.db.add(event)
        await self.db.flush()

        return self._event_out(event, attendees=0, revenue=0)

    async def update_event(self, event_id: int, data: EventUpdate) -> dict[str, Any] | None:
        event = await self._get_event(event_id)
        if event is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        current_schedule_type = self._normalize_schedule_type(getattr(event, "schedule_type", None))
        if "title" in payload:
            event.title = payload.get("title")
        if "description" in payload:
            event.description = payload.get("description")
        if "location" in payload:
            event.location = payload.get("location")
        if "status" in payload:
            status = payload.get("status")
            event.is_active = status == "active"
        if "date" in payload:
            date_value = payload.get("date")
            event.starts_at = datetime.combine(date_value, time.min) if date_value else None
            if current_schedule_type == EVENT_SCHEDULE_ONE_TIME:
                event.start_date = event.starts_at
        if "price" in payload:
            price = payload.get("price")
            event.price = Decimal(str(price)) if price is not None else None
        if "link_getcourse" in payload:
            event.link_getcourse = None
        if "schedule_type" in payload:
            current_schedule_type = self._normalize_schedule_type(payload.get("schedule_type"))
            event.schedule_type = current_schedule_type
        if "start_date" in payload:
            event.start_date = self._to_start_of_day(payload.get("start_date"))
        if "start_time" in payload:
            event.start_time = self._parse_hhmm(payload.get("start_time"))
        if "end_time" in payload:
            event.end_time = self._parse_hhmm(payload.get("end_time"))
        if "recurring_rule" in payload:
            event.recurring_rule = self._serialize_recurring_rule(
                self._normalize_recurring_rule(payload.get("recurring_rule"))
            )
        if "occurrence_dates" in payload:
            event.occurrence_dates = self._serialize_occurrence_dates(
                self._normalize_occurrence_dates(payload.get("occurrence_dates"))
            )
        if "pricing_options" in payload:
            pricing_options = self._normalize_pricing_options(payload.get("pricing_options"))
            event.pricing_options = self._serialize_pricing_options(pricing_options)
            if pricing_options:
                event.price = Decimal(str(pricing_options[0]["price_rub"]))
            elif "price" not in payload:
                event.price = None
        if "hosts" in payload:
            event.hosts = self._normalize_text_field(payload.get("hosts"))
        if "price_individual_rub" in payload:
            event.price_individual_rub = self._normalize_int_field(payload.get("price_individual_rub"))
        if "price_group_rub" in payload:
            event.price_group_rub = self._normalize_int_field(payload.get("price_group_rub"))
        if "duration_hint" in payload:
            event.duration_hint = self._normalize_text_field(payload.get("duration_hint"))
        if "booking_hint" in payload:
            event.booking_hint = self._normalize_text_field(payload.get("booking_hint"))

        if current_schedule_type == EVENT_SCHEDULE_ROLLING:
            event.starts_at = None
            event.start_date = None
            event.start_time = None
            event.end_time = None
            event.recurring_rule = None
            event.occurrence_dates = None
        elif current_schedule_type == EVENT_SCHEDULE_RECURRING:
            if event.start_time is None:
                event.start_time = DEFAULT_RECURRING_START_TIME
            if event.end_time is None:
                event.end_time = DEFAULT_RECURRING_END_TIME
            recurring_rule_value = self._normalize_recurring_rule(event.recurring_rule)
            occurrence_dates_value = self._normalize_occurrence_dates(getattr(event, "occurrence_dates", None))
            if recurring_rule_value is None and not occurrence_dates_value:
                recurring_rule_value = dict(DEFAULT_RECURRING_RULE)
            event.recurring_rule = self._serialize_recurring_rule(recurring_rule_value)
            if recurring_rule_value is not None:
                event.occurrence_dates = None
            if event.starts_at is not None:
                event.starts_at = None
        else:
            event.start_time = None
            event.end_time = None
            event.recurring_rule = None
            event.occurrence_dates = None
            if event.starts_at is not None:
                event.start_date = event.starts_at

        # Events are no longer linked directly to GetCourse in CRM.
        event.link_getcourse = None

        await self.db.flush()

        attendees = await self._get_attendees(event.id)
        revenue = await self._get_event_revenue(event.id)
        return self._event_out(event, attendees=attendees, revenue=revenue)

    async def delete_event(self, event_id: int) -> bool:
        event = await self._get_event(event_id)
        if event is None:
            return False
        await self.db.delete(event)
        await self.db.flush()
        return True

    async def list_attendees(
        self,
        event_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        event = await self._get_event(event_id)
        if event is None:
            return None

        total = await self.db.scalar(
            select(func.count(UserEvent.id))
            .where(UserEvent.event_id == event_id)
            .where(UserEvent.status != "cancelled")
        )

        rows = await self.db.execute(
            select(UserEvent.user_id)
            .where(UserEvent.event_id == event_id)
            .where(UserEvent.status != "cancelled")
            .order_by(UserEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        user_ids = [row[0] for row in rows]
        if not user_ids:
            return {"items": [], "total": int(total or 0)}

        users_rows = await self.db.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {user.id: user for user in users_rows.scalars().all()}
        ordered_users = [users_by_id[user_id] for user_id in user_ids if user_id in users_by_id]

        items = await self._build_client_items(ordered_users)
        return {"items": items, "total": int(total or 0)}

    async def add_attendee_by_tg_id(self, event_id: int, tg_id: int) -> dict[str, Any]:
        event = await self._get_event(event_id)
        if event is None:
            return {"ok": False, "error": "event_not_found"}

        user = await self._get_user_by_tg_id(tg_id)
        if user is None:
            return {"ok": False, "error": "user_not_found"}

        res = await self.db.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user.id, UserEvent.event_id == event_id)
            )
        )
        link = res.scalar_one_or_none()
        already = False
        if link:
            if link.status != "cancelled":
                already = True
            else:
                link.status = "registered"
        else:
            self.db.add(UserEvent(user_id=user.id, event_id=event_id, status="registered"))
        await self.db.flush()
        return {"ok": True, "already": already}

    async def remove_attendee_by_tg_id(self, event_id: int, tg_id: int) -> dict[str, Any]:
        event = await self._get_event(event_id)
        if event is None:
            return {"ok": False, "error": "event_not_found"}

        user = await self._get_user_by_tg_id(tg_id)
        if user is None:
            return {"ok": False, "error": "user_not_found"}

        res = await self.db.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user.id, UserEvent.event_id == event_id)
            )
        )
        link = res.scalar_one_or_none()
        if not link or link.status == "cancelled":
            return {"ok": True, "removed": False}

        link.status = "cancelled"
        await self.db.flush()
        return {"ok": True, "removed": True}

    async def add_attendee(
        self,
        event_id: int,
        user_id: int,
    ) -> tuple[dict[str, Any] | None, bool, bool]:
        event = await self._get_event(event_id)
        if event is None:
            return None, False, False

        user = await self._get_user(user_id)
        if user is None:
            return None, False, False

        link_res = await self.db.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user_id, UserEvent.event_id == event_id)
            )
        )
        link = link_res.scalar_one_or_none()
        existed = False
        if link:
            if link.status != "cancelled":
                existed = True
            else:
                link.status = "registered"
        else:
            self.db.add(UserEvent(user_id=user_id, event_id=event_id, status="registered"))

        await self.db.flush()

        items = await self._build_client_items([user])
        return items[0] if items else None, True, existed

    async def remove_attendee(self, event_id: int, user_id: int) -> tuple[bool, bool]:
        event = await self._get_event(event_id)
        if event is None:
            return False, False

        user = await self._get_user(user_id)
        if user is None:
            return False, False

        res = await self.db.execute(
            select(UserEvent).where(
                and_(UserEvent.user_id == user_id, UserEvent.event_id == event_id)
            )
        )
        link = res.scalar_one_or_none()
        if not link or link.status == "cancelled":
            return True, False

        link.status = "cancelled"
        await self.db.flush()
        return True, True

    async def create_payment_for_user(
        self,
        user_id: int | None = None,
        tg_id: int | None = None,
        event_id: int | None = None,
        amount: int = 0,
        currency: str = "RUB",
        source: str | None = None,
    ) -> dict[str, Any] | None:
        if amount <= 0:
            return None

        user = None
        if user_id is not None:
            user = await self._get_user(user_id)
        elif tg_id is not None:
            user = await self._get_user_by_tg_id(tg_id)

        if user is None:
            return None

        if event_id is not None:
            event = await self._get_event(event_id)
            if event is None:
                return None

        has_event_id = await self._payments_has_event_id()
        payment_out: dict[str, Any] | None = None
        if has_event_id:
            payment = Payment(
                user_id=user.id,
                event_id=event_id,
                amount=amount,
                currency=currency or "RUB",
                source=source or "admin",
                status="pending",
            )
            self.db.add(payment)
            await self.db.flush()
            payment_out = await self._payment_out(payment)
        else:
            now = datetime.utcnow()
            row = (
                await self.db.execute(
                    text(
                        """
                        INSERT INTO payments (user_id, amount, status, currency, source, created_at, updated_at)
                        VALUES (:user_id, :amount, 'pending', :currency, :source, :created_at, :updated_at)
                        RETURNING id, user_id, amount, status, source, currency, created_at, paid_at
                        """
                    ),
                    {
                        "user_id": user.id,
                        "amount": amount,
                        "currency": currency or "RUB",
                        "source": source or "admin",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            ).mappings().first()
            if row is None:
                return None
            name_parts = [user.first_name or "", user.last_name or ""]
            client_name = " ".join(part for part in name_parts if part).strip()
            if not client_name:
                client_name = user.username or f"User {user.id}"
            payment_out = {
                "id": int(row["id"]),
                "user_id": int(row["user_id"]),
                "client_name": client_name,
                "tg_id": user.tg_id,
                "event_id": None,
                "event_title": None,
                "amount": int(row["amount"] or 0),
                "currency": row["currency"] or "RUB",
                "status": row["status"],
                "source": row["source"],
                "created_at": row["created_at"],
                "paid_at": row["paid_at"],
            }

        now = datetime.utcnow()
        user.last_activity_at = now
        if not user.crm_stage:
            user.crm_stage = User.CRM_STAGE_NEW
        activity_service = ActivityService(self.db)
        await activity_service.upsert(
            user_id=user.id,
            last_activity_at=now,
            ai_increment=0,
        )
        await self.db.flush()
        return payment_out

    async def mark_payment_status(self, payment_id: int, status: str) -> dict[str, Any] | None:
        now = datetime.utcnow()
        if await self._payments_has_event_id():
            payment = await self._get_payment(payment_id)
            if payment is None:
                return None

            payment.status = status
            if status == "paid":
                payment.paid_at = now
                user = await self._get_user(payment.user_id)
                if user is not None:
                    user.crm_stage = self.stage_after_payment_paid(user.crm_stage)
                    user.last_activity_at = now
            else:
                payment.paid_at = None
            await self.db.flush()
            if status == "paid":
                activity_service = ActivityService(self.db)
                await activity_service.upsert(
                    user_id=payment.user_id,
                    last_activity_at=now,
                    ai_increment=0,
                )
            return await self._payment_out(payment)

        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE payments
                    SET status = :status,
                        paid_at = :paid_at,
                        updated_at = :updated_at
                    WHERE id = :payment_id
                    RETURNING id, user_id, amount, status, source, currency, created_at, paid_at
                    """
                ),
                {
                    "status": status,
                    "paid_at": now if status == "paid" else None,
                    "updated_at": now,
                    "payment_id": payment_id,
                },
            )
        ).mappings().first()
        if row is None:
            return None

        user = await self._get_user(int(row["user_id"]))
        if status == "paid" and user is not None:
            user.crm_stage = self.stage_after_payment_paid(user.crm_stage)
            user.last_activity_at = now
            activity_service = ActivityService(self.db)
            await activity_service.upsert(
                user_id=user.id,
                last_activity_at=now,
                ai_increment=0,
            )
        await self.db.flush()

        name_parts = [user.first_name or "", user.last_name or ""] if user else []
        client_name = " ".join(part for part in name_parts if part).strip() if user else ""
        if not client_name and user:
            client_name = user.username or f"User {user.id}"

        return {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "client_name": client_name or None,
            "tg_id": user.tg_id if user else None,
            "event_id": None,
            "event_title": None,
            "amount": int(row["amount"] or 0),
            "currency": row["currency"] or "RUB",
            "status": row["status"],
            "source": row["source"],
            "created_at": row["created_at"],
            "paid_at": row["paid_at"],
        }

    async def list_payments(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: int | None = None,
        event_id: int | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        has_event_id = await self._payments_has_event_id()
        if event_id is not None and not has_event_id:
            return {"items": [], "total": 0}

        columns = [
            Payment.id,
            Payment.user_id,
            Payment.amount,
            Payment.status,
            Payment.source,
            Payment.currency,
            Payment.created_at,
            Payment.paid_at,
        ]
        if has_event_id:
            columns.append(Payment.event_id)

        query = select(*columns)
        if user_id is not None:
            query = query.where(Payment.user_id == user_id)
        if has_event_id and event_id is not None:
            query = query.where(Payment.event_id == event_id)
        if status is not None:
            query = query.where(Payment.status == status)
        if date_from is not None:
            query = query.where(Payment.created_at >= date_from)
        if date_to is not None:
            query = query.where(Payment.created_at <= date_to)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.db.execute(
            query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        )

        items: list[dict[str, Any]] = []
        for row in rows:
            mapping = row._mapping
            row_event_id = mapping.get("event_id") if has_event_id else None
            user = await self._get_user(int(mapping["user_id"]))
            event_title = None
            if row_event_id is not None:
                event = await self._get_event(int(row_event_id))
                event_title = event.title if event else None

            name_parts = [user.first_name or "", user.last_name or ""] if user else []
            client_name = " ".join(part for part in name_parts if part).strip() if user else ""
            if not client_name and user:
                client_name = user.username or f"User {user.id}"

            items.append(
                {
                    "id": int(mapping["id"]),
                    "user_id": int(mapping["user_id"]),
                    "client_name": client_name or None,
                    "tg_id": user.tg_id if user else None,
                    "event_id": row_event_id,
                    "event_title": event_title,
                    "amount": int(mapping["amount"] or 0),
                    "currency": mapping["currency"] or "RUB",
                    "status": mapping["status"],
                    "source": mapping["source"],
                    "created_at": mapping["created_at"],
                    "paid_at": mapping["paid_at"],
                }
            )

        return {"items": items, "total": int(total or 0)}

    async def get_revenue_summary(self) -> dict[str, Any]:
        total = await self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid")
        )
        paid_count = await self.db.scalar(
            select(func.count(Payment.id)).where(Payment.status == "paid")
        )
        pending_count = await self.db.scalar(
            select(func.count(Payment.id)).where(Payment.status == "pending")
        )

        by_events: list[dict[str, Any]] = []
        if await self._payments_has_event_id():
            by_events_rows = await self.db.execute(
                select(
                    Event.id,
                    Event.title,
                    func.coalesce(func.sum(Payment.amount), 0),
                )
                .join(Payment, Payment.event_id == Event.id)
                .where(Payment.status == "paid")
                .group_by(Event.id, Event.title)
                .order_by(func.sum(Payment.amount).desc())
            )
            by_events = [
                {"event_id": row[0], "title": row[1], "revenue": int(row[2] or 0)}
                for row in by_events_rows
            ]

        by_clients_rows = await self.db.execute(
            select(
                User.id,
                func.concat(User.first_name, " ", func.coalesce(User.last_name, "")),
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .join(Payment, Payment.user_id == User.id)
            .where(Payment.status == "paid")
            .group_by(User.id, User.first_name, User.last_name)
            .order_by(func.sum(Payment.amount).desc())
        )
        by_clients = [
            {"user_id": row[0], "name": (row[1] or "").strip(), "revenue": int(row[2] or 0)}
            for row in by_clients_rows
        ]

        return {
            "total": int(total or 0),
            "paidCount": int(paid_count or 0),
            "pendingCount": int(pending_count or 0),
            "byEvents": by_events,
            "byClients": by_clients,
        }

    async def get_getcourse_summary(self) -> dict[str, Any]:
        integration = self.get_getcourse_integration()
        return await integration.summary()

    async def list_getcourse_events(self, limit: int = 50) -> dict[str, Any]:
        integration = self.get_getcourse_integration()
        events = await integration.list_webhook_events(limit=limit)
        items: list[dict[str, Any]] = []
        for event in events:
            amount_value = None
            if event.amount is not None:
                amount_value = float(event.amount)
            items.append(
                {
                    "id": int(event.id),
                    "received_at": event.received_at,
                    "event_type": event.event_type,
                    "user_email": event.user_email,
                    "deal_number": event.deal_number,
                    "amount": amount_value,
                    "currency": event.currency,
                    "status": event.status,
                }
            )
        return {"items": items, "total": len(items)}

    async def _get_user_by_any_id(self, user_id: int) -> User | None:
        user = await self._get_user(user_id)
        if user is not None:
            return user
        return await self._get_user_by_tg_id(user_id)

    async def _get_or_create_private_channel_subscription(self, user_id: int) -> UserSubscription | None:
        user = await self._get_user_by_any_id(user_id)
        if user is None:
            return None

        row = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user.id)
            .where(UserSubscription.product == "private_channel")
            .limit(1)
        )
        subscription = row.scalar_one_or_none()
        if subscription is not None:
            return subscription

        subscription = UserSubscription(
            user_id=user.id,
            product="private_channel",
            status="pending",
        )
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def _get_or_create_channel_invite(self, subscription_id: int) -> ChannelInvite:
        row = await self.db.execute(
            select(ChannelInvite)
            .where(ChannelInvite.subscription_id == subscription_id)
            .order_by(ChannelInvite.id.desc())
            .limit(1)
        )
        invite = row.scalar_one_or_none()
        if invite is not None:
            return invite

        invite = ChannelInvite(
            subscription_id=subscription_id,
            token=uuid4().hex,
        )
        self.db.add(invite)
        await self.db.flush()
        return invite

    async def _create_telegram_invite_url(self) -> str | None:
        channel_id = (os.getenv("TELEGRAM_PRIVATE_CHANNEL_ID") or "").strip()
        bot_token = (os.getenv("BOT_TOKEN") or "").strip()
        if not channel_id or not bot_token:
            return None

        endpoint = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
        payload = {
            "chat_id": channel_id,
            "member_limit": 1,
            "creates_join_request": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(endpoint, json=payload)
            if response.status_code != 200:
                return None
            body = response.json()
            if not body.get("ok"):
                return None
            invite_link = (body.get("result") or {}).get("invite_link")
            return str(invite_link).strip() if invite_link else None
        except Exception as e:
            logger.warning("Telegram invite creation failed: %s", e.__class__.__name__)
            return None

    @staticmethod
    def _private_channel_placeholder_url(token: str) -> str:
        template = (os.getenv("PRIVATE_CHANNEL_INVITE_URL_TEMPLATE") or "").strip()
        if template and "{token}" in template:
            return template.replace("{token}", token)
        return f"https://example.com/private-channel/{token}"

    @staticmethod
    def _private_channel_payment_url() -> str | None:
        value = (os.getenv("YOOMONEY_PAY_URL_PLACEHOLDER") or "").strip()
        return value or None

    async def _ensure_invite_url(self, invite: ChannelInvite) -> str:
        if invite.invite_url:
            return invite.invite_url

        telegram_invite = await self._create_telegram_invite_url()
        if telegram_invite:
            invite.invite_url = telegram_invite
            await self.db.flush()
            return telegram_invite

        placeholder = self._private_channel_placeholder_url(invite.token)
        invite.invite_url = placeholder
        await self.db.flush()
        return placeholder

    async def mark_private_channel_paid(self, user_id: int) -> dict[str, Any] | None:
        subscription = await self._get_or_create_private_channel_subscription(user_id)
        if subscription is None:
            return None

        now = datetime.utcnow()
        subscription.status = "paid"
        if subscription.paid_at is None:
            subscription.paid_at = now
        subscription.updated_at = now

        invite = await self._get_or_create_channel_invite(subscription.id)
        invite_url = await self._ensure_invite_url(invite)
        return {
            "ok": True,
            "user_id": int(subscription.user_id),
            "product": "private_channel",
            "status": subscription.status,
            "token": invite.token,
            "invite_url": invite_url,
            "payment_url": self._private_channel_payment_url(),
            "paid_at": subscription.paid_at,
        }

    async def get_private_channel_invite(self, user_id: int) -> dict[str, Any] | None:
        subscription = await self._get_or_create_private_channel_subscription(user_id)
        if subscription is None:
            return None

        payload: dict[str, Any] = {
            "ok": True,
            "user_id": int(subscription.user_id),
            "product": "private_channel",
            "status": subscription.status,
            "token": None,
            "invite_url": None,
            "payment_url": self._private_channel_payment_url(),
            "paid_at": subscription.paid_at,
        }

        if subscription.status != "paid":
            return payload

        invite = await self._get_or_create_channel_invite(subscription.id)
        payload["token"] = invite.token
        payload["invite_url"] = await self._ensure_invite_url(invite)
        return payload

    def get_getcourse_integration(self) -> GetCourseService:
        return GetCourseService(self.db)

    @staticmethod
    def _get_sync_cooldown_minutes() -> int:
        raw = (os.getenv("GETCOURSE_SYNC_COOLDOWN_MINUTES") or "").strip()
        try:
            value = int(raw) if raw else 360
        except Exception:
            value = 360
        return max(value, 0)

    @staticmethod
    def _get_sync_force_role() -> str:
        return (os.getenv("GETCOURSE_SYNC_FORCE_ROLE") or "admin").strip().lower()

    async def _try_acquire_getcourse_sync_lock(self) -> bool:
        row = await self.db.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": 2302142001},
        )
        return bool(row.scalar_one_or_none())

    async def _release_getcourse_sync_lock(self) -> None:
        await self.db.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": 2302142001},
        )

    async def sync_getcourse(
        self,
        *,
        sync_users: bool = True,
        sync_payments: bool = True,
        sync_catalog: bool = True,
        force: bool = False,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        integration = self.get_getcourse_integration()
        lock_acquired = False

        if force and (actor_role or "").strip().lower() != self._get_sync_force_role():
            raise PermissionError("Force sync is not allowed for this role")

        state = await integration._state()
        cooldown_minutes = self._get_sync_cooldown_minutes()
        if not force and cooldown_minutes > 0 and state.last_sync_at is not None:
            last_sync_at = state.last_sync_at
            if last_sync_at.tzinfo is None:
                last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(tz=timezone.utc)
            next_allowed_at = last_sync_at + timedelta(minutes=cooldown_minutes)
            if now_utc < next_allowed_at:
                raise GetCourseSyncCooldownError(
                    next_allowed_at=next_allowed_at,
                    cooldown_minutes=cooldown_minutes,
                )

        lock_acquired = await self._try_acquire_getcourse_sync_lock()
        if not lock_acquired:
            raise GetCourseSyncAlreadyRunningError("Sync already running")

        if not integration.enabled:
            await integration.save_sync_result(
                fetched=0,
                imported_events={"created": 0, "updated": 0, "skipped": 0, "no_date": 0, "bad_url": 0},
                imported_catalog={"created": 0, "updated": 0, "skipped": 0, "bad_url": 0},
                source_counts={},
                imported_users={"created": 0, "updated": 0, "skipped": 0},
                imported_payments={"created": 0, "updated": 0, "skipped": 0},
                resource_sync_at={"users": None, "payments": None, "catalog": None},
                error=None,
            )
            return await integration.summary()

        try:
            state.last_sync_at = datetime.utcnow()
            state.updated_at = datetime.utcnow()
            await self.db.flush()
            return await integration.summary()
        finally:
            if lock_acquired:
                await self._release_getcourse_sync_lock()
    def _normalize_gc_stage(self, value: Any) -> str:
        raw = str(value or "").strip().upper()
        if raw in User.CRM_STAGE_CHOICES:
            return raw
        return User.CRM_STAGE_ENGAGED

    def _normalize_gc_email(self, value: Any) -> str | None:
        text = str(value or "").strip().lower()
        if "@" not in text or "." not in text.split("@")[-1]:
            return None
        return text[:100]

    def _normalize_gc_phone(self, value: Any) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[:64]

    async def upsert_client_from_getcourse(self, payload_user: dict[str, Any]) -> str:
        external_id = str(payload_user.get("id") or payload_user.get("user_id") or "").strip()
        if not external_id:
            return "skipped"
        email = self._normalize_gc_email(payload_user.get("email"))
        phone = self._normalize_gc_phone(payload_user.get("phone") or payload_user.get("phone_number"))
        first_name = str(payload_user.get("first_name") or payload_user.get("name") or "").strip() or None
        last_name = str(payload_user.get("last_name") or "").strip() or None
        username = str(payload_user.get("username") or payload_user.get("login") or "").strip().lstrip("@") or None
        stage = self._normalize_gc_stage(payload_user.get("crm_stage"))
        updated_at = self._to_datetime(payload_user.get("updated_at") or payload_user.get("created_at"))

        user: User | None = None
        if email:
            row = await self.db.execute(select(User).where(User.email == email))
            user = row.scalar_one_or_none()
        if user is None and phone:
            row = await self.db.execute(select(User).where(User.phone == phone))
            user = row.scalar_one_or_none()

        if user is None:
            user = User(
                tg_id=await self._generate_tg_id(),
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                phone=phone,
                source=User.SOURCE_COURSE,
                crm_stage=stage,
                last_activity_at=updated_at,
            )
            self.db.add(user)
            return "created"

        has_changes = False
        for field_name, new_value in (
            ("first_name", first_name),
            ("last_name", last_name),
            ("username", username),
            ("email", email),
            ("phone", phone),
        ):
            if new_value and getattr(user, field_name) != new_value:
                setattr(user, field_name, new_value)
                has_changes = True
        if user.crm_stage != stage:
            user.crm_stage = stage
            has_changes = True
        if updated_at and user.last_activity_at != updated_at:
            user.last_activity_at = updated_at
            has_changes = True
        return "updated" if has_changes else "skipped"

    async def upsert_payment_from_getcourse(self, payload_payment: dict[str, Any]) -> str:
        external_id = str(
            payload_payment.get("id")
            or payload_payment.get("payment_id")
            or payload_payment.get("transaction_id")
            or ""
        ).strip()
        if not external_id:
            return "skipped"

        user_email = self._normalize_gc_email(payload_payment.get("user_email") or payload_payment.get("email"))
        user_phone = self._normalize_gc_phone(payload_payment.get("user_phone") or payload_payment.get("phone"))
        user: User | None = None
        if user_email:
            row = await self.db.execute(select(User).where(User.email == user_email))
            user = row.scalar_one_or_none()
        if user is None and user_phone:
            row = await self.db.execute(select(User).where(User.phone == user_phone))
            user = row.scalar_one_or_none()
        if user is None:
            return "skipped"

        amount_raw = payload_payment.get("amount") or payload_payment.get("sum") or payload_payment.get("price")
        try:
            amount_value = int(Decimal(str(amount_raw))) if amount_raw not in (None, "") else 0
        except Exception:
            amount_value = 0
        if amount_value <= 0:
            return "skipped"

        status_raw = str(payload_payment.get("status") or "").strip().lower()
        status = "pending"
        if status_raw in {"paid", "success", "succeeded", "done", "completed"}:
            status = "paid"
        elif status_raw in {"failed", "error"}:
            status = "failed"
        elif status_raw in {"cancelled", "canceled"}:
            status = "cancelled"

        row = await self.db.execute(
            select(Payment).where(Payment.source == "getcourse").where(Payment.external_id == external_id)
        )
        payment = row.scalar_one_or_none()
        if payment is None:
            payment = Payment(
                user_id=user.id,
                amount=amount_value,
                status=status,
                source="getcourse",
                external_id=external_id,
                currency=str(payload_payment.get("currency") or "RUB"),
            )
            self.db.add(payment)
            if status == "paid":
                user.crm_stage = User.CRM_STAGE_PAID
            return "created"

        has_changes = False
        for field_name, new_value in (
            ("amount", amount_value),
            ("status", status),
            ("currency", str(payload_payment.get("currency") or payment.currency or "RUB")),
        ):
            if getattr(payment, field_name) != new_value:
                setattr(payment, field_name, new_value)
                has_changes = True
        if status == "paid" and user.crm_stage != User.CRM_STAGE_PAID:
            user.crm_stage = User.CRM_STAGE_PAID
        return "updated" if has_changes else "skipped"

    async def upsert_catalog_item_from_getcourse(self, payload_program: dict[str, Any], integration: GetCourseService) -> str:
        dto = integration._build_entity(str(payload_program.get("_gc_source") or "catalog"), payload_program)
        if dto is None:
            return "skipped"
        mapped = integration.normalize_entity_to_catalog_fields(dto)
        if mapped.get("url_error"):
            return "bad_url"
        external_id = str(mapped["external_id"])
        item = await self._get_catalog_by_external("getcourse", external_id)
        if item is None:
            item = CatalogItem(
                title=mapped["title"],
                description=mapped["description"],
                price=Decimal(str(mapped["price"])) if mapped.get("price") is not None else None,
                currency=mapped.get("currency") or "RUB",
                link_getcourse=mapped.get("link_getcourse"),
                item_type=mapped.get("item_type") or "product",
                status=mapped.get("status") or "active",
                external_source="getcourse",
                external_id=external_id,
                external_updated_at=mapped.get("external_updated_at"),
            )
            self.db.add(item)
            return "created"

        has_changes = False
        for field_name in ("title", "description", "currency", "link_getcourse", "item_type", "status"):
            new_value = mapped.get(field_name)
            if getattr(item, field_name) != new_value:
                setattr(item, field_name, new_value)
                has_changes = True

        new_price = Decimal(str(mapped["price"])) if mapped.get("price") is not None else None
        if item.price != new_price:
            item.price = new_price
            has_changes = True
        if item.external_updated_at != mapped.get("external_updated_at"):
            item.external_updated_at = mapped.get("external_updated_at")
            has_changes = True
        return "updated" if has_changes else "skipped"

    @staticmethod
    def _to_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip().replace("Z", "+00:00")
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None
    async def sync_getcourse_events(
        self,
        entities: list[Any],
        integration: GetCourseService,
    ) -> dict[str, int]:
        created = 0
        updated = 0
        skipped = 0
        no_date = 0
        bad_url = 0

        for entity in entities:
            mapped = integration.normalize_entity_to_event_fields(entity)
            if mapped.get("url_error"):
                bad_url += 1
                logger.warning(
                    "Skip invalid event link_getcourse: external_id=%s source_field=%s reason=%s",
                    mapped.get("external_id"),
                    mapped.get("link_getcourse_source"),
                    mapped.get("url_error"),
                )
            if mapped.get("date") is None or mapped.get("starts_at") is None:
                no_date += 1
                continue

            external_id = str(mapped["external_id"])
            event = await self._get_event_by_external("getcourse", external_id)

            if event is None:
                event = Event(
                    title=mapped["title"],
                    description=mapped["description"],
                    location=mapped["location"],
                    link_getcourse=mapped["link_getcourse"],
                    starts_at=mapped["starts_at"],
                    price=Decimal(str(mapped["price"])) if mapped.get("price") is not None else None,
                    is_active=(mapped["status"] == "active"),
                    external_source="getcourse",
                    external_id=external_id,
                    external_updated_at=mapped.get("external_updated_at"),
                )
                self.db.add(event)
                created += 1
                continue

            has_changes = False

            for field_name in ("title", "description", "location", "link_getcourse"):
                new_value = mapped.get(field_name)
                if getattr(event, field_name) != new_value:
                    setattr(event, field_name, new_value)
                    has_changes = True

            new_starts_at = mapped.get("starts_at")
            if event.starts_at != new_starts_at:
                event.starts_at = new_starts_at
                has_changes = True

            new_price = Decimal(str(mapped["price"])) if mapped.get("price") is not None else None
            if event.price != new_price:
                event.price = new_price
                has_changes = True

            new_is_active = mapped["status"] == "active"
            if bool(event.is_active) != new_is_active:
                event.is_active = new_is_active
                has_changes = True

            new_external_updated_at = mapped.get("external_updated_at")
            if event.external_updated_at != new_external_updated_at:
                event.external_updated_at = new_external_updated_at
                has_changes = True

            if has_changes:
                updated += 1
            else:
                skipped += 1

        await self.db.flush()
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "no_date": no_date,
            "bad_url": bad_url,
        }

    async def sync_getcourse_catalog(
        self,
        entities: list[Any],
        integration: GetCourseService,
    ) -> dict[str, int]:
        created = 0
        updated = 0
        skipped = 0
        bad_url = 0

        for entity in entities:
            mapped = integration.normalize_entity_to_catalog_fields(entity)
            if mapped.get("url_error"):
                bad_url += 1
                logger.warning(
                    "Skip invalid catalog link_getcourse: external_id=%s source_field=%s reason=%s",
                    mapped.get("external_id"),
                    mapped.get("link_getcourse_source"),
                    mapped.get("url_error"),
                )
            external_id = str(mapped["external_id"])
            item = await self._get_catalog_by_external("getcourse", external_id)

            if item is None:
                item = CatalogItem(
                    title=mapped["title"],
                    description=mapped["description"],
                    price=Decimal(str(mapped["price"])) if mapped.get("price") is not None else None,
                    currency=mapped.get("currency") or "RUB",
                    link_getcourse=mapped.get("link_getcourse"),
                    item_type=mapped.get("item_type") or "product",
                    status=mapped.get("status") or "active",
                    external_source="getcourse",
                    external_id=external_id,
                    external_updated_at=mapped.get("external_updated_at"),
                )
                self.db.add(item)
                created += 1
                continue

            has_changes = False

            for field_name in ("title", "description", "currency", "link_getcourse", "item_type", "status"):
                new_value = mapped.get(field_name)
                if getattr(item, field_name) != new_value:
                    setattr(item, field_name, new_value)
                    has_changes = True

            new_price = Decimal(str(mapped["price"])) if mapped.get("price") is not None else None
            if item.price != new_price:
                item.price = new_price
                has_changes = True

            new_external_updated_at = mapped.get("external_updated_at")
            if item.external_updated_at != new_external_updated_at:
                item.external_updated_at = new_external_updated_at
                has_changes = True

            if has_changes:
                updated += 1
            else:
                skipped += 1

        await self.db.flush()
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "bad_url": bad_url,
        }

    async def _get_user(self, user_id: int) -> User | None:
        res = await self.db.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def _get_event(self, event_id: int) -> Event | None:
        res = await self.db.execute(select(Event).where(Event.id == event_id))
        return res.scalar_one_or_none()

    async def _get_event_by_external(self, source: str, external_id: str) -> Event | None:
        res = await self.db.execute(
            select(Event)
            .where(Event.external_source == source)
            .where(Event.external_id == external_id)
        )
        return res.scalar_one_or_none()

    async def _get_catalog_by_external(self, source: str, external_id: str) -> CatalogItem | None:
        res = await self.db.execute(
            select(CatalogItem)
            .where(CatalogItem.external_source == source)
            .where(CatalogItem.external_id == external_id)
        )
        return res.scalar_one_or_none()

    async def _get_user_by_tg_id(self, tg_id: int) -> User | None:
        res = await self.db.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()

    async def _get_payment(self, payment_id: int) -> Payment | None:
        res = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return res.scalar_one_or_none()

    async def _get_revenue(self, user_id: int) -> int:
        value = await self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.user_id == user_id)
            .where(Payment.status == "paid")
        )
        return int(value or 0)

    async def _get_attendees(self, event_id: int) -> int:
        value = await self.db.scalar(
            select(func.count(UserEvent.id))
            .where(UserEvent.event_id == event_id)
            .where(UserEvent.status != "cancelled")
        )
        return int(value or 0)

    async def _get_event_revenue(self, event_id: int) -> int:
        if not await self._payments_has_event_id():
            return 0
        value = await self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.event_id == event_id)
            .where(Payment.status == "paid")
        )
        return int(value or 0)

    async def _generate_tg_id(self) -> int:
        value = await self.db.scalar(select(func.max(User.tg_id)))
        if value is None:
            return 100000
        return int(value) + 1

    async def _build_client_items(self, users: list[User]) -> list[dict[str, Any]]:
        if not users:
            return []

        interested_ids = {user.interested_event_id for user in users if user.interested_event_id}
        interested_titles: dict[int, str] = {}
        if interested_ids:
            rows = await self.db.execute(
                select(Event.id, Event.title).where(Event.id.in_(interested_ids))
            )
            interested_titles = {row[0]: row[1] for row in rows}

        user_ids = [user.id for user in users]
        revenue_map: dict[int, int] = {}
        if user_ids:
            rows = await self.db.execute(
                select(
                    Payment.user_id,
                    func.coalesce(func.sum(Payment.amount), 0),
                )
                .where(Payment.user_id.in_(user_ids))
                .where(Payment.status == "paid")
                .group_by(Payment.user_id)
            )
            revenue_map = {row[0]: int(row[1] or 0) for row in rows}

        activity_map: dict[int, tuple[int, datetime | None]] = {}
        if user_ids:
            rows = await self.db.execute(
                select(
                    CRMUserActivity.user_id,
                    CRMUserActivity.ai_chats,
                    CRMUserActivity.last_activity_at,
                )
                .where(CRMUserActivity.user_id.in_(user_ids))
            )
            activity_map = {row[0]: (int(row[1] or 0), row[2]) for row in rows}

        return [
            self._client_out(
                user,
                revenue_map.get(user.id, 0),
                interested_titles.get(user.interested_event_id),
                activity_map.get(user.id),
            )
            for user in users
        ]

    async def _payment_out(self, payment: Payment) -> dict[str, Any]:
        user = await self._get_user(payment.user_id)
        event = await self._get_event(payment.event_id) if payment.event_id else None

        name_parts = [user.first_name or "", user.last_name or ""] if user else []
        name = " ".join(part for part in name_parts if part).strip() if user else ""
        if not name and user:
            name = user.username or f"User {user.id}"

        return {
            "id": payment.id,
            "user_id": payment.user_id,
            "client_name": name or None,
            "tg_id": user.tg_id if user else None,
            "event_id": payment.event_id,
            "event_title": event.title if event else None,
            "amount": int(payment.amount or 0),
            "currency": payment.currency or "RUB",
            "status": payment.status,
            "source": payment.source,
            "created_at": payment.created_at,
            "paid_at": payment.paid_at,
        }

    def _split_name(self, name: str) -> tuple[str | None, str | None]:
        parts = [part for part in name.split(" ") if part]
        if not parts:
            return None, None
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])

    def _normalize_username(self, telegram: str | None) -> str | None:
        if not telegram:
            return None
        return telegram.lstrip("@").strip()

    def _client_out(
        self,
        user: User,
        revenue: int,
        interested: str | None,
        activity: tuple[int, datetime | None] | None,
    ) -> dict[str, Any]:
        name_parts = [user.first_name or "", user.last_name or ""]
        name = " ".join(part for part in name_parts if part).strip()
        if not name:
            name = user.username or f"User {user.id}"

        status_label = DB_TO_STATUS.get(user.status, "\u041d\u043e\u0432\u044b\u0439")
        if user.is_vip:
            status_label = "VIP \u041a\u043b\u0438\u0435\u043d\u0442"
        stage_value = self.normalize_stage(user.crm_stage)

        registered = user.created_at.date().isoformat() if user.created_at else None
        ai_chats = activity[0] if activity else 0
        last_activity_at = user.last_activity_at or (activity[1] if activity else None) or user.updated_at
        last_activity = last_activity_at.isoformat() if last_activity_at else None

        ready_to_pay = bool(user.phone or user.email) or stage_value in {
            User.CRM_STAGE_READY_TO_PAY,
            User.CRM_STAGE_MANAGER_FOLLOWUP,
            User.CRM_STAGE_PAID,
        }
        needs_manager = stage_value == User.CRM_STAGE_MANAGER_FOLLOWUP

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "name": name,
            "telegram": f"@{user.username}" if user.username else None,
            "status": status_label,
            "stage": stage_value,
            "phone": user.phone,
            "email": user.email,
            "registered": registered,
            "interested": interested,
            "aiChats": int(ai_chats),
            "lastActivity": last_activity,
            "revenue": revenue,
            "flags": {
                "readyToPay": ready_to_pay,
                "needsManager": needs_manager,
            },
        }

    def _event_out(self, event: Event, attendees: int, revenue: int) -> dict[str, Any]:
        date_value = event.starts_at.date().isoformat() if event.starts_at else None
        start_date_raw = getattr(event, "start_date", None)
        start_date_value = start_date_raw.date().isoformat() if isinstance(start_date_raw, datetime) else (
            start_date_raw.isoformat() if start_date_raw else None
        )
        price_value: float | None = None
        if event.price is not None:
            if isinstance(event.price, Decimal):
                price_value = float(event.price)
            else:
                price_value = float(event.price)
        recurring_rule = self._normalize_recurring_rule(getattr(event, "recurring_rule", None))
        occurrence_dates = self._normalize_occurrence_dates(getattr(event, "occurrence_dates", None))
        pricing_options = self._normalize_pricing_options(getattr(event, "pricing_options", None))
        if pricing_options is None:
            pricing_options = self._pricing_options_fallback(event)
        if price_value is None and pricing_options:
            price_value = float(pricing_options[0]["price_rub"])
        schedule_type = self._normalize_schedule_type(getattr(event, "schedule_type", None))

        return {
            "id": event.id,
            "title": event.title,
            "type": "\u0421\u043e\u0431\u044b\u0442\u0438\u0435",
            "price": price_value,
            "attendees": attendees,
            "date": date_value,
            "status": "active" if event.is_active else "finished",
            "description": event.description,
            "location": event.location,
            "link_getcourse": normalize_getcourse_url(event.link_getcourse)[0],
            "revenue": revenue,
            "schedule_type": schedule_type,
            "start_date": start_date_value,
            "start_time": self._time_to_hhmm(getattr(event, "start_time", None)),
            "end_time": self._time_to_hhmm(getattr(event, "end_time", None)),
            "recurring_rule": recurring_rule,
            "occurrence_dates": [item.isoformat() for item in occurrence_dates] if occurrence_dates else None,
            "schedule_text": self._event_schedule_text(event, recurring_rule, occurrence_dates),
            "pricing_options": pricing_options,
            "hosts": getattr(event, "hosts", None),
            "price_individual_rub": getattr(event, "price_individual_rub", None),
            "price_group_rub": getattr(event, "price_group_rub", None),
            "duration_hint": getattr(event, "duration_hint", None),
            "booking_hint": getattr(event, "booking_hint", None),
        }

    def _pricing_options_fallback(self, event: Event) -> list[dict[str, Any]] | None:
        direct = self._normalize_pricing_options(getattr(event, "pricing_options", None))
        if direct:
            return direct

        if event.price is not None:
            if isinstance(event.price, Decimal):
                price_int = int(event.price)
            else:
                price_int = int(float(event.price))
            return [{"label": "Стоимость", "price_rub": price_int, "note": None}]

        options: list[dict[str, Any]] = []
        if getattr(event, "price_individual_rub", None) is not None:
            options.append({"label": "Индивидуально", "price_rub": int(event.price_individual_rub), "note": None})
        if getattr(event, "price_group_rub", None) is not None:
            options.append({"label": "Группа (за участника)", "price_rub": int(event.price_group_rub), "note": None})
        if options:
            return options
        return None

    def _event_summary(self, event: Event) -> dict[str, Any]:
        date_value = event.starts_at.date().isoformat() if event.starts_at else None
        recurring_rule = self._normalize_recurring_rule(getattr(event, "recurring_rule", None))
        occurrence_dates = self._normalize_occurrence_dates(getattr(event, "occurrence_dates", None))
        price_value: float | None = None
        if event.price is not None:
            if isinstance(event.price, Decimal):
                price_value = float(event.price)
            else:
                price_value = float(event.price)
        pricing_options = self._pricing_options_fallback(event)
        if price_value is None and pricing_options:
            price_value = float(pricing_options[0]["price_rub"])

        return {
            "id": event.id,
            "title": event.title,
            "date": date_value,
            "description": event.description,
            "location": event.location,
            "link_getcourse": normalize_getcourse_url(event.link_getcourse)[0],
            "price": price_value,
            "schedule_type": self._normalize_schedule_type(getattr(event, "schedule_type", None)),
            "schedule_text": self._event_schedule_text(event, recurring_rule, occurrence_dates),
            "occurrence_dates": [item.isoformat() for item in occurrence_dates] if occurrence_dates else None,
            "pricing_options": pricing_options,
            "hosts": getattr(event, "hosts", None),
            "price_individual_rub": getattr(event, "price_individual_rub", None),
            "price_group_rub": getattr(event, "price_group_rub", None),
        }

    def _catalog_out(self, item: CatalogItem) -> dict[str, Any]:
        price_value: float | None = None
        if item.price is not None:
            if isinstance(item.price, Decimal):
                price_value = float(item.price)
            else:
                price_value = float(item.price)

        return {
            "id": int(item.id),
            "title": item.title,
            "description": item.description,
            "price": price_value,
            "currency": item.currency or "RUB",
            "link_getcourse": normalize_getcourse_url(item.link_getcourse)[0],
            "item_type": item.item_type or "product",
            "status": item.status or "active",
            "external_source": item.external_source or "getcourse",
            "external_id": item.external_id,
            "external_updated_at": item.external_updated_at.isoformat() if item.external_updated_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }






