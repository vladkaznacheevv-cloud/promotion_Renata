from fastapi import FastAPI
import core.db.database as db
from core.db import Base
from core.models import User
from ..core.api.api import router

app = FastAPI(title="CRM for Psych Project")

@app.on_event("startup")
async def startup():
    db.init_db()
    assert db.engine is not None
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(router, prefix="/api")
