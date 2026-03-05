import os
import re

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.api.deps import get_db
from core.auth.models import AdminUser
from core.auth.security import decode_access_token, is_jwt_error

auth_scheme = HTTPBearer(auto_error=False)


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-secret")


def _get_jwt_exp_minutes() -> int:
    value = os.getenv("JWT_EXPIRES_MINUTES", "1440")
    try:
        return int(value)
    except ValueError:
        return 1440


_ALLOWED_EMAIL_SPLIT_RE = re.compile(r"[,\s;]+")


def _get_crm_allowed_emails() -> set[str] | None:
    raw = (os.getenv("CRM_ALLOWED_EMAILS") or "").strip()
    if not raw:
        return None
    items = [
        part.strip().lower()
        for part in _ALLOWED_EMAIL_SPLIT_RE.split(raw)
        if part and part.strip()
    ]
    return set(items) or None


def is_email_allowed(email: str | None) -> bool:
    allowed = _get_crm_allowed_emails()
    if not allowed:
        return True
    normalized = (email or "").strip().lower()
    return normalized in allowed


async def get_current_admin_user(
    creds: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = creds.credentials
    try:
        payload = decode_access_token(token, _get_jwt_secret())
    except Exception as e:
        if is_jwt_error(e):
            raise HTTPException(status_code=401, detail="Invalid token")
        raise

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    res = await db.execute(select(AdminUser).where(AdminUser.id == int(user_id)))
    user = res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    if not is_email_allowed(user.email):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    async def _checker(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _checker
