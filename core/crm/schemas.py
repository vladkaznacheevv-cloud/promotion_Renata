from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


ClientStatus = Literal["Новый", "В работе", "Клиент", "VIP Клиент"]
ClientStage = Literal["NEW", "ENGAGED", "READY_TO_PAY", "MANAGER_FOLLOWUP", "PAID", "INACTIVE"]
EventStatus = Literal["active", "finished"]
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


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    telegram: Optional[str] = None
    status: Optional[ClientStatus] = None
    interested_event_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    stage: Optional[ClientStage] = None


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


class EventCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    location: Optional[str] = None
    date: date
    price: Optional[float] = None
    status: EventStatus = "active"
    link_getcourse: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    date: Optional[date] = None
    price: Optional[float] = None
    status: Optional[EventStatus] = None
    link_getcourse: Optional[str] = None


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
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    no_date: int = 0


class GetCourseImportedOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    no_date: int = 0


class GetCourseImportedCatalogOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0


class GetCourseSummaryOut(BaseModel):
    enabled: bool
    status: Literal["OK", "ERROR", "DISABLED"]
    lastSyncAt: Optional[str]
    last_sync_at: Optional[str] = None
    counts: GetCourseCountsOut
    sourceUrl: Optional[str] = None
    lastError: Optional[str] = None
    ok: Optional[bool] = None
    fetched: Optional[int] = None
    imported: Optional[GetCourseImportedOut] = None
    importedEvents: Optional[GetCourseImportedOut] = None
    importedCatalog: Optional[GetCourseImportedCatalogOut] = None

