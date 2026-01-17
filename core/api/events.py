from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.events.models import Event
from core.events.schemas import EventCreate, EventUpdate, EventResponse
from core.events.service import EventService

router = APIRouter()


@router.get("/", response_model=List[EventResponse])
async def get_events(
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить мероприятия"""
    service = EventService(db)
    events = await service.get_active()
    
    if event_type:
        events = [e for e in events if e.type == event_type]
    if status:
        events = [e for e in events if e.status == status]
    
    return events


@router.get("/upcoming", response_model=List[EventResponse])
async def get_upcoming_events(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Получить предстоящие мероприятия"""
    service = EventService(db)
    return await service.get_upcoming(limit=limit)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Получить мероприятие по ID"""
    service = EventService(db)
    event = await service.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    return event


@router.post("/", response_model=EventResponse)
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать мероприятие"""
    service = EventService(db)
    return await service.create(event_data)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить мероприятие"""
    service = EventService(db)
    event = await service.update(event_id, event_data)
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    return event


@router.post("/{event_id}/register")
async def register_user(
    event_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Зарегистрировать пользователя на мероприятие"""
    service = EventService(db)
    return await service.register_user(user_id=user_id, event_id=event_id)