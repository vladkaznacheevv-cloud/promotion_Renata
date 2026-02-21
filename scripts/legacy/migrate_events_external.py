import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db


STATEMENTS = [
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS link_getcourse TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_source TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_id TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_updated_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_events_external_source ON events (external_source)",
    "CREATE INDEX IF NOT EXISTS ix_events_external_id ON events (external_id)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_events_external_source_id
    ON events (external_source, external_id)
    WHERE external_source IS NOT NULL AND external_id IS NOT NULL
    """,
]


async def main():
    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.exec_driver_sql(statement)
    print("events external schema migrated")


if __name__ == "__main__":
    asyncio.run(main())

