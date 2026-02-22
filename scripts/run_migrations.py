import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db


MIGRATIONS = [
    ("payments", [
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
    ]),
    ("events_external", [
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
    ]),
    ("events_schedule_meta", [
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS schedule_type VARCHAR(20) DEFAULT 'one_time'",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS start_time TIME",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS end_time TIME",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS recurring_rule TEXT",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS occurrence_dates TEXT",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS pricing_options TEXT",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS hosts TEXT",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS price_individual_rub INTEGER",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS price_group_rub INTEGER",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS duration_hint TEXT",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS booking_hint TEXT",
        """
        UPDATE events
        SET schedule_type = CASE
            WHEN starts_at IS NULL THEN 'rolling'
            ELSE 'one_time'
        END
        WHERE schedule_type IS NULL OR schedule_type = ''
        """,
        "UPDATE events SET start_date = starts_at WHERE start_date IS NULL AND starts_at IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_events_schedule_type ON events (schedule_type)",
    ]),
    ("funnel_contacts", [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS crm_stage TEXT DEFAULT 'NEW'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ",
        "UPDATE users SET crm_stage = 'NEW' WHERE crm_stage IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_users_crm_stage ON users (crm_stage)",
    ]),
    ("catalog", [
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
    ]),
    ("integration_state", [
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
    ]),
    ("getcourse_webhook_events", [
        """
        CREATE TABLE IF NOT EXISTS getcourse_webhook_events (
            id SERIAL PRIMARY KEY,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            event_id VARCHAR(128) NULL,
            payload_hash VARCHAR(64) NULL,
            dedupe_key VARCHAR(160) NULL,
            event_type VARCHAR(100) NOT NULL DEFAULT 'unknown',
            user_email VARCHAR(255) NULL,
            user_id VARCHAR(100) NULL,
            deal_id VARCHAR(100) NULL,
            deal_number VARCHAR(100) NULL,
            amount NUMERIC(12,2) NULL,
            currency VARCHAR(16) NULL,
            status VARCHAR(64) NULL,
            raw_payload TEXT NOT NULL
        )
        """,
        "ALTER TABLE getcourse_webhook_events ADD COLUMN IF NOT EXISTS event_id VARCHAR(128)",
        "ALTER TABLE getcourse_webhook_events ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64)",
        "ALTER TABLE getcourse_webhook_events ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(160)",
        """
        UPDATE getcourse_webhook_events
        SET payload_hash = md5(raw_payload)
        WHERE payload_hash IS NULL
        """,
        """
        UPDATE getcourse_webhook_events
        SET dedupe_key = CASE
            WHEN event_id IS NOT NULL AND event_id <> '' THEN 'id:' || event_id
            ELSE 'hash:' || payload_hash
        END
        WHERE dedupe_key IS NULL
        """,
        """
        DELETE FROM getcourse_webhook_events a
        USING getcourse_webhook_events b
        WHERE a.id > b.id AND a.dedupe_key = b.dedupe_key
        """,
        "ALTER TABLE getcourse_webhook_events ALTER COLUMN payload_hash SET NOT NULL",
        "ALTER TABLE getcourse_webhook_events ALTER COLUMN dedupe_key SET NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_received_at ON getcourse_webhook_events (received_at)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_event_id ON getcourse_webhook_events (event_id)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_payload_hash ON getcourse_webhook_events (payload_hash)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_getcourse_webhook_events_dedupe_key ON getcourse_webhook_events (dedupe_key)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_event_type ON getcourse_webhook_events (event_type)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_user_email ON getcourse_webhook_events (user_email)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_user_id ON getcourse_webhook_events (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_deal_id ON getcourse_webhook_events (deal_id)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_deal_number ON getcourse_webhook_events (deal_number)",
        "CREATE INDEX IF NOT EXISTS ix_getcourse_webhook_events_status ON getcourse_webhook_events (status)",
    ]),
    ("private_channel_subscriptions", [
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product VARCHAR(64) NOT NULL DEFAULT 'private_channel',
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            paid_at TIMESTAMPTZ NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_user_subscriptions_user_id ON user_subscriptions (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_subscriptions_status ON user_subscriptions (status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_user_subscriptions_user_product ON user_subscriptions (user_id, product)",
        """
        CREATE TABLE IF NOT EXISTS channel_invites (
            id SERIAL PRIMARY KEY,
            subscription_id INTEGER NOT NULL REFERENCES user_subscriptions(id) ON DELETE CASCADE,
            token VARCHAR(64) NOT NULL,
            invite_url TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            used_at TIMESTAMPTZ NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_channel_invites_subscription_id ON channel_invites (subscription_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_channel_invites_token ON channel_invites (token)",
    ]),
]


async def main():
    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        for migration_name, statements in MIGRATIONS:
            print(f"[migrate] {migration_name}: start")
            for statement in statements:
                await conn.exec_driver_sql(statement)
            print(f"[migrate] {migration_name}: done")
    print("[migrate] all migrations done")


if __name__ == "__main__":
    asyncio.run(main())
