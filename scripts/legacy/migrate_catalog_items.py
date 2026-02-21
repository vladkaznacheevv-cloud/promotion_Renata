import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db


STATEMENTS = [
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS title TEXT",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS price NUMERIC(12,2)",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'RUB'",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS link_getcourse TEXT",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS item_type VARCHAR(20) DEFAULT 'product'",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_source VARCHAR(50) DEFAULT 'getcourse'",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_id VARCHAR(255)",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_updated_at TIMESTAMPTZ",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS ix_catalog_items_external_id ON catalog_items (external_id)",
    "CREATE INDEX IF NOT EXISTS ix_catalog_items_item_type ON catalog_items (item_type)",
    "CREATE INDEX IF NOT EXISTS ix_catalog_items_status ON catalog_items (status)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_catalog_items_external_source_id
    ON catalog_items (external_source, external_id)
    """,
]


async def main():
    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.exec_driver_sql(statement)
    print("catalog schema migrated")


if __name__ == "__main__":
    asyncio.run(main())

