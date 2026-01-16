import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.events.models import Event, UserEvent
from core.events.schemas import EventCreate, EventUpdate

logger = logging.getLogger(__name__)

class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, data: EventCreate) -> Event:
        event = Event(**data.model_dump())
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        logger.info(f"Мероприятие создано: id={event.id}, title={event.title}")
        return event
    
    async def get_by_id(self, event_id: int) -> Optional[Event]:
        result = await self.session.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active(self) -> List[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.status == Event.STATUS_PUBLISHED)
            .order_by(Event.date)
        )
        return result.scalars().all()
    
    async def get_upcoming(self, limit: int = 10) -> List[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.status == Event.STATUS_PUBLISHED, Event.date >= func.now())
            .order_by(Event.date)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update(self, event_id: int, data: EventUpdate) -> Optional[Event]:
        event = await self.get_by_id(event_id)
        if event:
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(event, key, value)
            await self.session.commit()
            logger.info(f"Мероприятие обновлено: id={event_id}")
            return event
        return None
    
    async def register_user(self, user_id: int, event_id: int) -> UserEvent:
        """Зарегистрировать пользователя на мероприятие"""
        participant = UserEvent(
            user_id=user_id,
            event_id=event_id,
            status=UserEvent.STATUS_REGISTERED
        )
        self.session.add(participant)
        
        # Увеличиваем счётчик проданных мест
        event = await self.get_by_id(event_id)
        if event:
            event.seats_sold += 1
            participant.status = UserEvent.STATUS_CONFIRMED
        
        await self.session.commit()
        await self.session.refresh(participant)
        logger.info(f"Пользователь {user_id} зарегистрирован на мероприятие {event_id}")
        return participant
    
    async def get_participants(self, event_id: int) -> List[UserEvent]:
        result = await self.session.execute(
            select(UserEvent).where(UserEvent.event_id == event_id)
        )
        return result.scalars().all()