import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from core.db import database as db

# API роутеры
from core.api.users import router as users_router
from core.api.events import router as events_router
from core.api.consultations import router as consultations_router
from core.api.payments import router as payments_router
from core.api.analytics import router as analytics_router
from core.api.ai import router as ai_router
from core.crm.api import router as crm_router

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """События при запуске/остановке"""
    logger.info("🚀 Renata Promotion API запускается...")
    yield
    logger.info("🛑 Renata Promotion API остановлен")


# Создаём приложение
app = FastAPI(
    title="Renata Promotion API",
    description="API для управления мероприятиями, консультациями и платежами",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(users_router, prefix="/api/users", tags=["Пользователи"])
app.include_router(events_router, prefix="/api/events", tags=["Мероприятия"])
app.include_router(consultations_router, prefix="/api/consultations", tags=["Консультации"])
app.include_router(payments_router, prefix="/api/payments", tags=["Платежи"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Аналитика"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI-чат"])
app.include_router(crm_router, prefix="/api/crm", tags=["CRM"])


# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "message": "Renata Promotion API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "core.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True
    )
