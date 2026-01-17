from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.analytics.service import AnalyticsService

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Дашборд с основной статистикой"""
    service = AnalyticsService(db)
    return await service.get_dashboard_stats()


@router.get("/users/activity")
async def get_user_activity(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Активность пользователей по дням"""
    service = AnalyticsService(db)
    return await service.get_user_activity(days=days)


@router.get("/revenue/by-product")
async def get_revenue_by_product(db: AsyncSession = Depends(get_db)):
    """Выручка по типам продуктов"""
    service = AnalyticsService(db)
    return await service.get_revenue_by_product()