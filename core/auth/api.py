from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.auth.deps import (
    get_current_admin_user,
    _get_jwt_secret,
    _get_jwt_exp_minutes,
    is_email_allowed,
)
from core.auth.models import AdminUser
from core.auth.schemas import LoginRequest, LoginResponse, AuthMeResponse
from core.auth.security import verify_password, create_access_token

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    if not is_email_allowed(payload.email):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    res = await db.execute(select(AdminUser).where(AdminUser.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        secret=_get_jwt_secret(),
        expires_minutes=_get_jwt_exp_minutes(),
    )

    return {
        "access_token": token,
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@router.get("/me", response_model=AuthMeResponse)
async def me(user: AdminUser = Depends(get_current_admin_user)):
    return {"user": {"id": user.id, "email": user.email, "role": user.role}}


@router.post("/logout")
async def logout():
    # Stateless JWT: logout handled on client by removing token
    return {"status": "ok"}
