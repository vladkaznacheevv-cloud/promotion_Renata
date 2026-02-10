from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.schemas import ClientCreate, ClientUpdate, EventCreate, EventUpdate
from core.crm.models import CRMUserActivity
from core.crm.activity_service import ActivityService
from core.catalog.models import CatalogItem
from core.events.models import Event, UserEvent
from core.integrations.getcourse import GetCourseService
from core.payments.models import Payment
from core.users.models import User


STATUS_TO_DB = {
    "РќРѕРІС‹Р№": User.STATUS_NEW,
    "Р’ СЂР°Р±РѕС‚Рµ": User.STATUS_IN_WORK,
    "РљР»РёРµРЅС‚": User.STATUS_CLIENT,
    "VIP РљР»РёРµРЅС‚": User.STATUS_VIP,
}

DB_TO_STATUS = {
    User.STATUS_NEW: "РќРѕРІС‹Р№",
    User.STATUS_IN_WORK: "Р’ СЂР°Р±РѕС‚Рµ",
    User.STATUS_CLIENT: "РљР»РёРµРЅС‚",
    User.STATUS_VIP: "VIP РљР»РёРµРЅС‚",
}


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
        query = select(User)

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
        limit: int = 20,
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
        status_label = payload.get("status") or "РќРѕРІС‹Р№"
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
            link_getcourse=payload.get("link_getcourse"),
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
        if "link_getcourse" in payload:
            event.link_getcourse = payload.get("link_getcourse")

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
        integration = GetCourseService(self.db)
        return await integration.summary()

    async def sync_getcourse(self) -> dict[str, Any]:
        integration = GetCourseService(self.db)
        if not integration.enabled:
            await integration.save_sync_result(
                fetched=0,
                imported_events={"created": 0, "updated": 0, "skipped": 0, "no_date": 0},
                imported_catalog={"created": 0, "updated": 0, "skipped": 0},
                source_counts={},
                error="GetCourse integration is disabled or API key is missing",
            )
            return await integration.summary()

        try:
            entities, source_counts = await integration.fetch_entities()
            dated_entities, undated_catalog = integration.split_entities(entities)
            imported_events = await self.sync_getcourse_events(dated_entities, integration)
            imported_events["no_date"] = int(imported_events.get("no_date", 0)) + len(undated_catalog)
            imported_catalog = await self.sync_getcourse_catalog(undated_catalog, integration)
            await integration.save_sync_result(
                fetched=len(entities),
                imported_events=imported_events,
                imported_catalog=imported_catalog,
                source_counts=source_counts,
                error=None,
            )
            return await integration.summary()
        except Exception as exc:
            await integration.save_sync_result(
                fetched=0,
                imported_events={"created": 0, "updated": 0, "skipped": 0, "no_date": 0},
                imported_catalog={"created": 0, "updated": 0, "skipped": 0},
                source_counts={},
                error=str(exc),
            )
            return await integration.summary()

    async def sync_getcourse_events(
        self,
        entities: list[Any],
        integration: GetCourseService,
    ) -> dict[str, int]:
        created = 0
        updated = 0
        skipped = 0
        no_date = 0

        for entity in entities:
            mapped = integration.normalize_entity_to_event_fields(entity)
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
        }

    async def sync_getcourse_catalog(
        self,
        entities: list[Any],
        integration: GetCourseService,
    ) -> dict[str, int]:
        created = 0
        updated = 0
        skipped = 0

        for entity in entities:
            mapped = integration.normalize_entity_to_catalog_fields(entity)
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

        status_label = DB_TO_STATUS.get(user.status, "РќРѕРІС‹Р№")
        if user.is_vip:
            status_label = "VIP РљР»РёРµРЅС‚"
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
        price_value: float | None = None
        if event.price is not None:
            if isinstance(event.price, Decimal):
                price_value = float(event.price)
            else:
                price_value = float(event.price)

        return {
            "id": event.id,
            "title": event.title,
            "type": "РЎРѕР±С‹С‚РёРµ",
            "price": price_value,
            "attendees": attendees,
            "date": date_value,
            "status": "active" if event.is_active else "finished",
            "description": event.description,
            "location": event.location,
            "link_getcourse": event.link_getcourse,
            "revenue": revenue,
        }

    def _event_summary(self, event: Event) -> dict[str, Any]:
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
            "date": date_value,
            "description": event.description,
            "location": event.location,
            "link_getcourse": event.link_getcourse,
            "price": price_value,
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
            "link_getcourse": item.link_getcourse,
            "item_type": item.item_type or "product",
            "status": item.status or "active",
            "external_source": item.external_source or "getcourse",
            "external_id": item.external_id,
            "external_updated_at": item.external_updated_at.isoformat() if item.external_updated_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }




