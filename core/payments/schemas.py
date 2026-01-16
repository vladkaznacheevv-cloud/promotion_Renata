from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PaymentCreate(BaseModel):
    user_id: int
    amount: int  # в копейках!
    currency: str = 'RUB'
    product_type: str
    product_id: Optional[int] = None
    description: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    currency: str
    product_type: str
    status: str
    payment_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True