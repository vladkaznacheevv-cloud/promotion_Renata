from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Схема для создания пользователя
class UserCreate(BaseModel):
    tg_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: str = 'bot'

# Схема для обновления пользователя
class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    is_vip: Optional[bool] = None
    vip_until: Optional[datetime] = None

# Схема для ответа
class UserResponse(BaseModel):
    id: int
    tg_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    is_vip: bool
    status: str
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True