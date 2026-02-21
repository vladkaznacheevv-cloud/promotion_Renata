import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db


STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS integration_state (
        id SERIAL PRIMARY KEY,
        name VARCHAR(64) NOT NULL UNIQUE,
        last_sync_at TIMESTAMPTZ NULL,
        last_error TEXT NULL,
        payload_json TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_integration_state_name ON integration_state (name)",
]


async def main():
    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.exec_driver_sql(statement)
    print("integration_state schema migrated")


if __name__ == "__main__":
    asyncio.run(main())

