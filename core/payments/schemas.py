from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    user_id: int
    amount: int  # в копейках
    provider: Optional[str] = None
    external_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    status: str
    provider: Optional[str]
    external_id: Optional[str]
    metadata_: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
