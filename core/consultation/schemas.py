from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

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