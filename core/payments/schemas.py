from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class PaymentCreate(BaseModel):
    user_id: int
    amount: int  # в копейках
    provider: Optional[str] = None
    external_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: Optional[int]
    status: str
    provider: Optional[str]
    external_id: Optional[str]
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
