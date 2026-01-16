from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class EventCreate(BaseModel):
    type: str
    title: str
    description: Optional[str] = None
    date: datetime
    location: Optional[str] = None
    address: Optional[str] = None
    price: Optional[str] = None
    seats_total: int = 0

class EventUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[str] = None
    price: Optional[str] = None
    status: Optional[str] = None
    seats_total: Optional[int] = None

class EventResponse(BaseModel):
    id: int
    type: str
    title: str
    description: Optional[str]
    date: datetime
    location: Optional[str]
    price: Optional[str]
    status: str
    seats_total: int
    seats_sold: int
    seats_available: int
    image_url: Optional[str]
    
    class Config:
        from_attributes = True