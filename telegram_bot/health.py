from __future__ import annotations

import asyncio
import importlib
import sys

from sqlalchemy import text

from core.db import database as db


def _check_imports() -> None:
    # Import runtime-critical modules without touching Telegram network APIs.
    modules = (
        "telegram_bot.keyboards",
        "telegram_bot.lock_utils",
        "core.crm.service",
    )
    for module in modules:
        importlib.import_module(module)


async def _check_db() -> None:
    db.init_db()
    if db.async_session is None:
        raise RuntimeError("Database session is not initialized")
    async with db.async_session() as session:
        await session.execute(text("SELECT 1"))


def main() -> int:
    try:
        _check_imports()
    except Exception:
        print("health import check failed")
        return 1
    try:
        asyncio.run(_check_db())
    except Exception:
        print("health db check failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
