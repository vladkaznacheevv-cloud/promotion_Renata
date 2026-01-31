from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.schemas import ClientCreate, ClientUpdate, EventCreate, EventUpdate
from core.events.models import Event, UserEvent
from core.payments.models import Payment
from core.users.models import User


STATUS_TO_DB = {
    "Новый": User.STATUS_NEW,
    "В работе": User.STATUS_IN_WORK,
    "Клиент": User.STATUS_CLIENT,
    "VIP Клиент": User.STATUS_VIP,
}

DB_TO_STATUS = {
    User.STATUS_NEW: "Новый",
    User.STATUS_IN_WORK: "В работе",
    User.STATUS_CLIENT: "Клиент",
    User.STATUS_VIP: "VIP Клиент",
}


@dataclass
class CRMService:
    db: AsyncSession

    async def list_clients(self, limit: int = 10) -> dict[str, Any]:
        total = await self.db.scalar(select(func.count(User.id)))

        result = await self.db.execute(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
        users = result.scalars().all()

        interested_ids = {user.interested_event_id for user in users if user.interested_event_id}
        interested_titles: dict[int, str] = {}
        if interested_ids:
            rows = await self.db.execute(
                select(Event.id, Event.title).where(Event.id.in_(interested_ids))
            )
            interested_titles = {row.id: row.title for row in rows}

        user_ids = [user.id for user in users]
        revenue_map: dict[int, int] = {}
        if user_ids:
            rows = await self.db.execute(
                select(
                    Payment.user_id,
                    func.coalesce(func.sum(Payment.amount), 0),
                )
                .where(Payment.user_id.in_(user_ids))
                .group_by(Payment.user_id)
            )
            revenue_map = {row[0]: int(row[1] or 0) for row in rows}

        items = [
            self._client_out(user, revenue_map.get(user.id, 0), interested_titles.get(user.interested_event_id))
            for user in users
        ]

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
                .group_by(UserEvent.event_id)
            )
            attendees_map = {row[0]: int(row[1]) for row in rows}

        items = [self._event_out(event, attendees_map.get(event.id, 0)) for event in events]
        return {"items": items, "total": int(total or 0)}

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
        status_label = payload.get("status") or "Новый"
        status_code = STATUS_TO_DB.get(status_label, User.STATUS_NEW)

        user = User(
            tg_id=tg_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            status=status_code,
            source="crm",
            is_vip=status_code == User.STATUS_VIP,
            interested_event_id=payload.get("interested_event_id"),
        )
        self.db.add(user)
        await self.db.flush()

        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(
                select(Event.title).where(Event.id == user.interested_event_id)
            )
            interested_title = row.scalar_one_or_none()

        return self._client_out(user, revenue=0, interested=interested_title)

    async def update_client(self, client_id: int, data: ClientUpdate) -> dict[str, Any] | None:
        user = await self._get_user(client_id)
        if user is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "name" in payload:
            first_name, last_name = self._split_name(payload.get("name") or "")
            user.first_name = first_name
            user.last_name = last_name
        if "telegram" in payload:
            user.username = self._normalize_username(payload.get("telegram"))
        if "status" in payload:
            status_label = payload.get("status")
            status_code = STATUS_TO_DB.get(status_label, User.STATUS_NEW)
            user.status = status_code
            user.is_vip = status_code == User.STATUS_VIP
        if "interested_event_id" in payload:
            user.interested_event_id = payload.get("interested_event_id")

        await self.db.flush()

        interested_title = None
        if user.interested_event_id:
            row = await self.db.execute(
                select(Event.title).where(Event.id == user.interested_event_id)
            )
            interested_title = row.scalar_one_or_none()

        revenue = await self._get_revenue(user.id)
        return self._client_out(user, revenue=revenue, interested=interested_title)

    async def delete_client(self, client_id: int) -> bool:
        user = await self._get_user(client_id)
        if user is None:
            return False
        await self.db.delete(user)
        await self.db.flush()
        return True

    async def create_event(self, data: EventCreate) -> dict[str, Any]:
        payload = data.model_dump()
        status = payload.get("status") or "active"
        is_active = status == "active"

        starts_at = None
        if payload.get("date"):
            starts_at = datetime.combine(payload["date"], time.min)

        price = payload.get("price")
        if price is not None:
            price = Decimal(str(price))

        event = Event(
            title=payload.get("title"),
            description=payload.get("description"),
            location=payload.get("location"),
            starts_at=starts_at,
            price=price,
            is_active=is_active,
        )
        self.db.add(event)
        await self.db.flush()

        return self._event_out(event, attendees=0)

    async def update_event(self, event_id: int, data: EventUpdate) -> dict[str, Any] | None:
        event = await self._get_event(event_id)
        if event is None:
            return None

        payload = data.model_dump(exclude_unset=True)
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
        if "price" in payload:
            price = payload.get("price")
            event.price = Decimal(str(price)) if price is not None else None

        await self.db.flush()

        attendees = await self._get_attendees(event.id)
        return self._event_out(event, attendees=attendees)

    async def delete_event(self, event_id: int) -> bool:
        event = await self._get_event(event_id)
        if event is None:
            return False
        await self.db.delete(event)
        await self.db.flush()
        return True

    async def _get_user(self, user_id: int) -> User | None:
        res = await self.db.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def _get_event(self, event_id: int) -> Event | None:
        res = await self.db.execute(select(Event).where(Event.id == event_id))
        return res.scalar_one_or_none()

    async def _get_revenue(self, user_id: int) -> int:
        value = await self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.user_id == user_id)
        )
        return int(value or 0)

    async def _get_attendees(self, event_id: int) -> int:
        value = await self.db.scalar(
            select(func.count(UserEvent.id)).where(UserEvent.event_id == event_id)
        )
        return int(value or 0)

    async def _generate_tg_id(self) -> int:
        value = await self.db.scalar(select(func.max(User.tg_id)))
        if value is None:
            return 100000
        return int(value) + 1

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

    def _client_out(self, user: User, revenue: int, interested: str | None) -> dict[str, Any]:
        name_parts = [user.first_name or "", user.last_name or ""]
        name = " ".join(part for part in name_parts if part).strip()
        if not name:
            name = user.username or f"User {user.id}"

        status_label = DB_TO_STATUS.get(user.status, "Новый")
        if user.is_vip:
            status_label = "VIP Клиент"

        registered = user.created_at.date().isoformat() if user.created_at else None
        last_activity = user.updated_at.date().isoformat() if user.updated_at else None

        return {
            "id": user.id,
            "name": name,
            "telegram": f"@{user.username}" if user.username else None,
            "status": status_label,
            "registered": registered,
            "interested": interested,
            "aiChats": 0,
            "lastActivity": last_activity,
            "revenue": revenue,
        }

    def _event_out(self, event: Event, attendees: int) -> dict[str, Any]:
        date_value = event.starts_at.date().isoformat() if event.starts_at else None
        price_value: float | None = None
        if event.price is not None:
            if isinstance(event.price, Decimal):
                price_value = float(event.price)
            else:
                price_value = float(event.price)

        return {
            "id": event.id,
            "title": event.title,
            "type": "Событие",
            "price": price_value,
            "attendees": attendees,
            "date": date_value,
            "status": "active" if event.is_active else "finished",
            "description": event.description,
            "location": event.location,
            "revenue": 0,
        }
