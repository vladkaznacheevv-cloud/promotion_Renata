import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db
from core.db import Base
from sqlalchemy import select, update, func

from core.auth.models import AdminUser
from core.auth.security import hash_password


async def main():
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    role = os.getenv("ADMIN_ROLE", "admin")
    upsert = (os.getenv("ADMIN_UPSERT", "0").strip().lower() in {"1", "true", "yes"})
    enforce_single = (os.getenv("ADMIN_ENFORCE_SINGLE", "0").strip().lower() in {"1", "true", "yes"})

    if not email or not password:
        raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD env vars")

    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AdminUser.__table__])
    async with db.async_session() as session:
        res = await session.execute(
            select(AdminUser).where(func.lower(AdminUser.email) == email.lower())
        )
        existing = res.scalar_one_or_none()
        if existing:
            if not upsert:
                print("Admin user already exists")
                return

            existing.password_hash = hash_password(password)
            existing.role = role
            existing.is_active = True

            if enforce_single:
                await session.execute(
                    update(AdminUser)
                    .where(func.lower(AdminUser.email) != email.lower())
                    .values(is_active=False)
                )

            await session.commit()
            print(f"Updated admin user ({role})")
            return

        user = AdminUser(
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        if enforce_single:
            await session.execute(
                update(AdminUser)
                .where(func.lower(AdminUser.email) != email.lower())
                .values(is_active=False)
            )
        await session.commit()
        print(f"Created admin user ({role})")


if __name__ == "__main__":
    asyncio.run(main())
