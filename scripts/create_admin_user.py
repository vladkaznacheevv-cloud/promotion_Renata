import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db
from core.db import Base
from sqlalchemy import select

from core.auth.models import AdminUser
from core.auth.security import hash_password


async def main():
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    role = os.getenv("ADMIN_ROLE", "admin")

    if not email or not password:
        raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD env vars")

    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AdminUser.__table__])
    async with db.async_session() as session:
        res = await session.execute(select(AdminUser).where(AdminUser.email == email))
        existing = res.scalar_one_or_none()
        if existing:
            print("Admin user already exists")
            return

        user = AdminUser(
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Created admin user: {email} ({role})")


if __name__ == "__main__":
    asyncio.run(main())
