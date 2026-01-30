from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ConsultationUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None
    available_slots: Optional[int] = None
    is_active: Optional[bool] = None


class ConsultationCreate(BaseModel):
    type: str
    title: str
    description: Optional[str] = None
    duration_minutes: int = 60
    price: Optional[float] = None
    available_slots: Optional[int] = None
    is_active: bool = True


class ConsultationResponse(BaseModel):
    id: int
    type: str
    title: str
    description: Optional[str]
    duration_minutes: Optional[int]
    price: Optional[float]
    available_slots: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
