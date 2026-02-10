import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.db import Base
from core.db import database as db
from core.auth.models import AdminUser
from core.crm.api import router as crm_router
from core.crm.models import CRMUserActivity, IntegrationState
from core.auth.api import router as auth_router
from core.api.ai import router as ai_router
from core.api.analytics import router as analytics_router
from core.api.consultations import router as consultations_router
from core.api.events import router as events_router
from core.api.payments import router as payments_router
from core.api.users import router as users_router
from core.events.models import Event
from core.payments.models import Payment
from core.catalog.models import CatalogItem

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    logger.info("Renata Promotion API startup")
    try:
        db.init_db()
        logger.info("DB initialized")

        if db.engine is not None:
            async with db.engine.begin() as conn:
                await conn.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        CRMUserActivity.__table__,
                        IntegrationState.__table__,
                        AdminUser.__table__,
                        Payment.__table__,
                        Event.__table__,
                        CatalogItem.__table__,
                    ],
                )
                logger.info("CRM activity table ensured")

                # Backward-compatible schema patch for old DBs without payment fields.
                await conn.exec_driver_sql(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS event_id BIGINT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'RUB'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS source TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ"
                )
                await conn.exec_driver_sql(
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
                    """
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_payments_event_id ON payments (event_id)"
                )
                logger.info("Payments schema ensured")

                await conn.exec_driver_sql(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS link_getcourse TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_source TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_id TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS external_updated_at TIMESTAMPTZ"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_events_external_source ON events (external_source)"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_events_external_id ON events (external_id)"
                )
                await conn.exec_driver_sql(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_events_external_source_id
                    ON events (external_source, external_id)
                    WHERE external_source IS NOT NULL AND external_id IS NOT NULL
                    """
                )
                logger.info("Events schema ensured")

                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS title TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS description TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS price NUMERIC(12,2)"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'RUB'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS link_getcourse TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS item_type VARCHAR(20) DEFAULT 'product'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_source VARCHAR(50) DEFAULT 'getcourse'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_id VARCHAR(255)"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS external_updated_at TIMESTAMPTZ"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_items_external_id ON catalog_items (external_id)"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_items_item_type ON catalog_items (item_type)"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_items_status ON catalog_items (status)"
                )
                await conn.exec_driver_sql(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_catalog_items_external_source_id
                    ON catalog_items (external_source, external_id)
                    """
                )
                logger.info("Catalog schema ensured")

                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100)"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS crm_stage TEXT DEFAULT 'NEW'"
                )
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ"
                )
                await conn.exec_driver_sql(
                    "UPDATE users SET crm_stage = 'NEW' WHERE crm_stage IS NULL"
                )
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_users_crm_stage ON users (crm_stage)"
                )
                logger.info("Users funnel schema ensured")
    except Exception:
        logger.exception("DB init failed")

    yield
    logger.info("Renata Promotion API shutdown")


app = FastAPI(
    title="Renata Promotion API",
    description="API for events, consultations and payments",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(events_router, prefix="/api/events", tags=["Events"])
app.include_router(consultations_router, prefix="/api/consultations", tags=["Consultations"])
app.include_router(payments_router, prefix="/api/payments", tags=["Payments"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(crm_router, prefix="/api/crm", tags=["CRM"])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "message": "Renata Promotion API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "core.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
