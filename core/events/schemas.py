from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    price: Optional[Decimal] = None
    capacity: Optional[int] = None
    is_active: bool = True


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    price: Optional[Decimal] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    location: Optional[str]
    price: Optional[Decimal]
    capacity: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
