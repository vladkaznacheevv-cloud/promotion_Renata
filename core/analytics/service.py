import logging
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from core.users.models import User
from core.events.models import Event, UserEvent
from core.payments.models import Payment
from core.consultations.models import Consultation, UserConsultation

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_dashboard_stats(self) -> Dict:
        """Получить статистику для дашборда"""
        
        # Пользователи
        total_users = await self.session.execute(select(func.count(User.id)))
        total_users = total_users.scalar() or 0
        
        new_users = await self.session.execute(
            select(func.count(User.id)).where(User.status == User.STATUS_NEW)
        )
        new_users = new_users.scalar() or 0
        
        vip_users = await self.session.execute(
            select(func.count(User.id)).where(User.is_vip == True)
        )
        vip_users = vip_users.scalar() or 0
        
        # Мероприятия
        active_events = await self.session.execute(
            select(func.count(Event.id)).where(Event.status == Event.STATUS_PUBLISHED)
        )
        active_events = active_events.scalar() or 0
        
        total_participants = await self.session.execute(
            select(func.count(UserEvent.id))
        )
        total_participants = total_participants.scalar() or 0
        
        # Платежи
        total_revenue = await self.session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == Payment.STATUS_PAID)
        )
        total_revenue = total_revenue.scalar() or 0
        
        pending_payments = await self.session.execute(
            select(func.count(Payment.id)).where(Payment.status == Payment.STATUS_PENDING)
        )
        pending_payments = pending_payments.scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "new": new_users,
                "vip": vip_users
            },
            "events": {
                "active": active_events,
                "participants": total_participants
            },
            "payments": {
                "total_revenue": total_revenue,
                "pending": pending_payments
            }
        }
    
    async def get_user_activity(self, days: int = 7) -> List[dict]:
        """Активность пользователей по дням"""
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            )
            .where(User.created_at >= start_date)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        
        return [{"date": str(row.date), "count": row.count} for row in result.all()]
    
    async def get_revenue_by_product(self) -> Dict[str, int]:
        """Выручка по типам продуктов"""
        result = await self.session.execute(
            select(
                Payment.product_type,
                func.sum(Payment.amount).label('total')
            )
            .where(Payment.status == Payment.STATUS_PAID)
            .group_by(Payment.product_type)
        )
        
        return {row.product_type: row.total or 0 for row in result.all()}