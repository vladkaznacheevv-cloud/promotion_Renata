import asyncio

from sqlalchemy import text

from core.db import database as db


async def main() -> None:
    db.init_db()
    if db.async_session is None:
        raise RuntimeError("DB is not initialized")

    async with db.async_session() as session:
        await session.execute(text("SELECT 1"))
        await session.commit()

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
