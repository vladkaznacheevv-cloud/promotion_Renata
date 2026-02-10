from datetime import datetime
from typing import Literal

from pydantic import BaseModel


RoleType = Literal["admin", "manager", "viewer"]


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUserOut(BaseModel):
    id: int
    email: str
    role: RoleType


class LoginResponse(BaseModel):
    access_token: str
    user: AuthUserOut


class AuthMeResponse(BaseModel):
    user: AuthUserOut


class AdminUserCreate(BaseModel):
    email: str
    password: str
    role: RoleType = "admin"


class AdminUserOut(BaseModel):
    id: int
    email: str
    role: RoleType
    is_active: bool
    created_at: datetime
