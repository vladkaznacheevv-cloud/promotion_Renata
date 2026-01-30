from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    price: Optional[float] = None
    capacity: Optional[int] = None
    is_active: bool = True


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    price: Optional[float] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    location: Optional[str]
    price: Optional[float]
    capacity: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
