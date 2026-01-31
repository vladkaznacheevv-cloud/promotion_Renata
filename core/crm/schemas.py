from __future__ import annotations

from datetime import date
from typing import List, Optional, Literal

from pydantic import BaseModel


ClientStatus = Literal["Новый", "В работе", "Клиент", "VIP Клиент"]
EventStatus = Literal["active", "finished"]


class ClientCreate(BaseModel):
    name: str
    telegram: Optional[str] = None
    status: Optional[ClientStatus] = "Новый"
    tg_id: Optional[int] = None
    interested_event_id: Optional[int] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    telegram: Optional[str] = None
    status: Optional[ClientStatus] = None
    interested_event_id: Optional[int] = None


class ClientOut(BaseModel):
    id: int
    name: str
    telegram: Optional[str]
    status: str
    registered: Optional[str]
    interested: Optional[str]
    aiChats: int
    lastActivity: Optional[str]
    revenue: int


class ClientsOut(BaseModel):
    items: List[ClientOut]
    total: int


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    date: Optional[date] = None
    price: Optional[float] = None
    status: Optional[EventStatus] = "active"


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    date: Optional[date] = None
    price: Optional[float] = None
    status: Optional[EventStatus] = None


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
    revenue: int


class EventsOut(BaseModel):
    items: List[EventOut]
    total: int


class AiTopQuestion(BaseModel):
    question: str
    count: int


class AiStatsOut(BaseModel):
    totalResponses: int
    activeUsers: int
    avgRating: float
    responseTime: float
    topQuestions: List[AiTopQuestion]
