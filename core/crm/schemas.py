from __future__ import annotations

from datetime import date as dt_date, datetime
from typing import Any, List, Optional, Literal

from pydantic import BaseModel, Field, model_validator


ClientStatus = Literal["Новый", "В работе", "Клиент", "VIP Клиент"]
ClientStage = Literal["NEW", "ENGAGED", "READY_TO_PAY", "MANAGER_FOLLOWUP", "PAID", "INACTIVE"]
EventStatus = Literal["active", "finished"]
EventScheduleType = Literal["one_time", "recurring", "rolling"]
CatalogType = Literal["course", "product"]
CatalogStatus = Literal["active", "archived"]


class ClientCreate(BaseModel):
    name: str
    telegram: Optional[str] = None
    status: Optional[ClientStatus] = "Новый"
    tg_id: Optional[int] = None
    interested_event_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    stage: Optional[ClientStage] = None
    tags: Optional[List[str]] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    telegram: Optional[str] = None
    status: Optional[ClientStatus] = None
    interested_event_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    tags: Optional[List[str]] = None
    needs_manager_call: Optional[bool] = None


class ClientFlags(BaseModel):
    readyToPay: bool = False
    needsManager: bool = False


class ClientOut(BaseModel):
    id: int
    tg_id: Optional[int]
    name: str
    telegram: Optional[str]
    status: str
    stage: ClientStage
    tags: List[str] = Field(default_factory=list)
    needs_manager_call: bool = False
    phone: Optional[str]
    email: Optional[str]
    registered: Optional[str]
    interested: Optional[str]
    aiChats: int
    lastActivity: Optional[str]
    revenue: int
    flags: ClientFlags


class ClientsOut(BaseModel):
    items: List[ClientOut]
    total: int


class ClientNeedsCallIn(BaseModel):
    value: bool


class ClientActivityOut(BaseModel):
    id: int
    client_id: int
    created_at: datetime
    actor: str
    action: str
    meta: dict[str, Any] = Field(default_factory=dict)


class PricingOption(BaseModel):
    label: str = Field(min_length=1)
    price_rub: int = Field(ge=0)
    note: Optional[str] = None


def _validate_event_schedule(
    *,
    schedule_type: str | None,
    date_value: dt_date | None,
    start_date_value: dt_date | None,
    occurrence_dates: list[dt_date] | None,
) -> None:
    normalized = (schedule_type or "one_time").strip().lower() or "one_time"
    has_occurrence_dates = bool(occurrence_dates)

    if normalized == "rolling":
        if date_value is not None:
            raise ValueError("date must be null for rolling events")
        if start_date_value is not None:
            raise ValueError("start_date must be null for rolling events")
        if has_occurrence_dates:
            raise ValueError("occurrence_dates must be empty for rolling events")
        return

    if normalized == "one_time":
        if date_value is None:
            raise ValueError("date is required for one_time events")
        return

    if normalized == "recurring":
        if start_date_value is None:
            raise ValueError("start_date is required for recurring events")
        return


class EventCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    location: Optional[str] = None
    date: Optional[dt_date] = None
    price: Optional[float] = None
    status: EventStatus = "active"
    link_getcourse: Optional[str] = None
    schedule_type: Optional[EventScheduleType] = None
    start_date: Optional[dt_date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurring_rule: Optional[dict[str, Any]] = None
    occurrence_dates: Optional[List[dt_date]] = None
    pricing_options: Optional[List[PricingOption]] = None
    hosts: Optional[str] = None
    price_individual_rub: Optional[int] = None
    price_group_rub: Optional[int] = None
    duration_hint: Optional[str] = None
    booking_hint: Optional[str] = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "EventCreate":
        _validate_event_schedule(
            schedule_type=self.schedule_type,
            date_value=self.date,
            start_date_value=self.start_date,
            occurrence_dates=self.occurrence_dates,
        )
        if (self.schedule_type or "one_time") == "recurring":
            if not self.recurring_rule and not self.occurrence_dates:
                raise ValueError("recurring events require recurring_rule or occurrence_dates")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    date: Optional[dt_date] = None
    price: Optional[float] = None
    status: Optional[EventStatus] = None
    link_getcourse: Optional[str] = None
    schedule_type: Optional[EventScheduleType] = None
    start_date: Optional[dt_date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurring_rule: Optional[dict[str, Any]] = None
    occurrence_dates: Optional[List[dt_date]] = None
    pricing_options: Optional[List[PricingOption]] = None
    hosts: Optional[str] = None
    price_individual_rub: Optional[int] = None
    price_group_rub: Optional[int] = None
    duration_hint: Optional[str] = None
    booking_hint: Optional[str] = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "EventUpdate":
        normalized = (self.schedule_type or "").strip().lower()
        provided = self.model_fields_set
        if normalized == "rolling":
            _validate_event_schedule(
                schedule_type="rolling",
                date_value=self.date if "date" in provided else None,
                start_date_value=self.start_date if "start_date" in provided else None,
                occurrence_dates=self.occurrence_dates if "occurrence_dates" in provided else None,
            )
        elif normalized == "one_time" and "date" in provided and self.date is None:
            raise ValueError("date is required when schedule_type is one_time")
        elif normalized == "recurring":
            if "start_date" in provided and self.start_date is None:
                raise ValueError("start_date is required when schedule_type is recurring")
            if {"recurring_rule", "occurrence_dates"} & provided:
                if not self.recurring_rule and not self.occurrence_dates:
                    raise ValueError("recurring events require recurring_rule or occurrence_dates")
        return self


class EventOut(BaseModel):
    id: int
    title: str
    type: str
    price: Optional[float]
    attendees: int
    date: Optional[str]
    status: str
    description: Optional[str]
    location: Optional[str]
    link_getcourse: Optional[str]
    revenue: int
    schedule_type: Optional[EventScheduleType] = None
    start_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurring_rule: Optional[dict[str, Any]] = None
    occurrence_dates: Optional[List[str]] = None
    schedule_text: Optional[str] = None
    pricing_options: Optional[List[PricingOption]] = None
    hosts: Optional[str] = None
    price_individual_rub: Optional[int] = None
    price_group_rub: Optional[int] = None
    duration_hint: Optional[str] = None
    booking_hint: Optional[str] = None


class EventsOut(BaseModel):
    items: List[EventOut]
    total: int


class CatalogItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    price: Optional[float]
    currency: str = "RUB"
    link_getcourse: Optional[str]
    item_type: CatalogType
    status: CatalogStatus
    external_source: str
    external_id: str
    external_updated_at: Optional[str] = None
    updated_at: Optional[str] = None


class CatalogListOut(BaseModel):
    items: List[CatalogItemOut]
    total: int


class AttendeeCreate(BaseModel):
    client_id: Optional[int] = None
    tg_id: Optional[int] = None


class AttendeesOut(BaseModel):
    items: List[ClientOut]
    total: int


class TgIdRequest(BaseModel):
    tg_id: int


class AiTopQuestion(BaseModel):
    question: str
    count: int


class AiStatsOut(BaseModel):
    totalResponses: int
    activeUsers: int
    avgRating: float
    responseTime: float
    topQuestions: List[AiTopQuestion]


class DashboardSummaryOut(BaseModel):
    days: Literal[7, 30, 90]
    start_ts: datetime
    end_ts: datetime
    ai_answers: int
    new_clients: int
    payments_count: int
    revenue_total: int


class PaymentStatus(BaseModel):
    value: Literal["pending", "paid", "failed", "cancelled"]


class PaymentCreateIn(BaseModel):
    user_id: Optional[int] = None
    tg_id: Optional[int] = None
    event_id: Optional[int] = None
    amount: int
    currency: Optional[str] = "RUB"
    source: Optional[str] = "admin"


class PaymentUpdateIn(BaseModel):
    status: Literal["pending", "paid", "failed", "cancelled"]


class PaymentOut(BaseModel):
    id: int
    user_id: int
    client_name: Optional[str]
    tg_id: Optional[int]
    event_id: Optional[int]
    event_title: Optional[str]
    amount: int
    currency: str
    status: str
    source: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]


class PaymentsOut(BaseModel):
    items: List[PaymentOut]
    total: int


class RevenueByEvent(BaseModel):
    event_id: int
    title: str
    revenue: int


class RevenueByClient(BaseModel):
    user_id: int
    name: str
    revenue: int


class RevenueSummaryOut(BaseModel):
    total: int
    paidCount: int
    pendingCount: int
    byEvents: List[RevenueByEvent]
    byClients: List[RevenueByClient]


class GetCourseCountsOut(BaseModel):
    courses: int = 0
    products: int = 0
    events: int = 0
    catalog_items: int = 0
    users: int = 0
    payments: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    no_date: int = 0
    bad_url: int = 0


class GetCourseImportedOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    no_date: int = 0
    bad_url: int = 0


class GetCourseImportedCatalogOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    bad_url: int = 0


class GetCourseSummaryOut(BaseModel):
    enabled: bool
    has_key: Optional[bool] = None
    base_url: Optional[str] = None
    status: Literal["OK", "ERROR", "DISABLED"]
    lastSyncAt: Optional[str] = None
    last_sync_at: Optional[str] = None
    last_event_at: Optional[str] = None
    events_last_24h: Optional[int] = 0
    events_last_7d: Optional[int] = 0
    counts: GetCourseCountsOut
    sourceUrl: Optional[str] = None
    lastError: Optional[str] = None
    last_error: Optional[str] = None
    ok: Optional[bool] = None
    fetched: Optional[int] = None
    imported: Optional[GetCourseImportedOut] = None
    importedEvents: Optional[GetCourseImportedOut] = None
    importedCatalog: Optional[GetCourseImportedCatalogOut] = None
    importedUsers: Optional[GetCourseImportedCatalogOut] = None
    importedPayments: Optional[GetCourseImportedCatalogOut] = None
    syncAtByResource: Optional[dict] = None
    unsupportedResources: Optional[list[str]] = None


class GetCourseResourceStatusOut(BaseModel):
    ok: bool
    status_code: Optional[int] = None
    error_kind: Optional[str] = None


class GetCourseDiagnoseOut(BaseModel):
    enabled: bool
    has_key: bool
    base_url: Optional[str] = None
    resourceStatuses: dict[str, GetCourseResourceStatusOut]
    unsupportedResources: list[str]
    fatalAuthError: bool
    successfulResources: list[str]


class GetCourseWebhookEventOut(BaseModel):
    id: int
    received_at: datetime
    event_type: str
    user_email: Optional[str] = None
    deal_number: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None


class GetCourseWebhookEventsOut(BaseModel):
    items: list[GetCourseWebhookEventOut]
    total: int


class PrivateChannelInviteOut(BaseModel):
    ok: bool = True
    user_id: int
    product: str = "private_channel"
    status: Literal["pending", "paid", "revoked"]
    token: Optional[str] = None
    invite_url: Optional[str] = None
    payment_url: Optional[str] = None
    paid_at: Optional[datetime] = None
