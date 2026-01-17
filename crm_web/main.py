from fastapi import FastAPI
from core.database import engine, Base
from core.models import User
from ..core.api.api import router

app = FastAPI(title="CRM for Psych Project")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(router, prefix="/api")