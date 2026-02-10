from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.crm.models import CRMUserActivity


class ActivityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, user_id: int, last_activity_at: datetime, ai_increment: int = 0) -> CRMUserActivity:
        res = await self.session.execute(
            select(CRMUserActivity).where(CRMUserActivity.user_id == user_id)
        )
        activity = res.scalar_one_or_none()
        if activity is None:
            activity = CRMUserActivity(
                user_id=user_id,
                ai_chats=max(ai_increment, 0),
                last_activity_at=last_activity_at,
            )
            self.session.add(activity)
        else:
            activity.last_activity_at = last_activity_at
            if ai_increment:
                activity.ai_chats = (activity.ai_chats or 0) + ai_increment
        await self.session.flush()
        return activity
