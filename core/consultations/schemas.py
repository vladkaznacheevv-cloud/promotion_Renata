from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ConsultationUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[str] = None
    available_slots: Optional[str] = None
    is_active: Optional[bool] = None

class ConsultationCreate(BaseModel):
    type: str
    title: str
    description: Optional[str] = None
    duration_minutes: int = 60
    price: Optional[str] = None
    available_slots: Optional[str] = None

class ConsultationResponse(BaseModel):
    id: int
    type: str
    title: str
    description: Optional[str]
    duration_minutes: int
    price: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True