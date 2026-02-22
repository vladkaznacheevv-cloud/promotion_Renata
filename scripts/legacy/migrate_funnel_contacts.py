import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db


async def main():
    db.init_db()
    assert db.engine is not None

    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS crm_stage TEXT DEFAULT 'NEW'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ",
        "UPDATE users SET crm_stage = 'NEW' WHERE crm_stage IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_users_crm_stage ON users (crm_stage)",
    ]

    async with db.engine.begin() as conn:
        for stmt in statements:
            await conn.exec_driver_sql(stmt)

    print("users funnel/contacts schema migrated")


if __name__ == "__main__":
    asyncio.run(main())
