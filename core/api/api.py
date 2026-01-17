# core/api/api.py

from fastapi import FastAPI
from core.api.users import router as users_router
from core.api.events import router as events_router
from core.api.consultations import router as consultations_router
from core.api.payments import router as payments_router
from core.api.analytics import router as analytics_router
from core.api.ai import router as ai_router

app = FastAPI(title="Renata Promotion API")

app.include_router(users_router, prefix="/api/users", tags=["Пользователи"])
app.include_router(events_router, prefix="/api/events", tags=["Мероприятия"])
app.include_router(consultations_router, prefix="/api/consultations", tags=["Консультации"])
app.include_router(payments_router, prefix="/api/payments", tags=["Платежи"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Аналитика"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI-чат"])


@app.get("/")
async def root():
    return {
        "message": "Renata Promotion API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}