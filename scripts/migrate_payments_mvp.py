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
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS event_id BIGINT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'RUB'",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS source TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'payments_event_id_fkey'
            ) THEN
                ALTER TABLE payments
                ADD CONSTRAINT payments_event_id_fkey
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """,
        "CREATE INDEX IF NOT EXISTS ix_payments_event_id ON payments (event_id)",
    ]

    async with db.engine.begin() as conn:
        for stmt in statements:
            await conn.exec_driver_sql(stmt)
    print("payments schema migrated")


if __name__ == "__main__":
    asyncio.run(main())
