from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.crm.schemas import (
    AiStatsOut,
    ClientCreate,
    ClientOut,
    ClientUpdate,
    ClientsOut,
    EventCreate,
    EventOut,
    EventUpdate,
    EventsOut,
)
from core.crm.service import CRMService

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"status": "ok"}


@router.get("/clients", response_model=ClientsOut)
async def get_clients(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    return await service.list_clients(limit=limit)


@router.post("/clients", response_model=ClientOut)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    return await service.create_client(payload)


@router.patch("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    result = await service.update_client(client_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return result


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    ok = await service.delete_client(client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted"}


@router.get("/events", response_model=EventsOut)
async def get_events(
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    return await service.list_events(limit=limit, status=status)


@router.post("/events", response_model=EventOut)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    return await service.create_event(payload)


@router.patch("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    result = await service.update_event(event_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = CRMService(db)
    ok = await service.delete_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted"}


@router.get("/ai/stats", response_model=AiStatsOut)
async def get_ai_stats(db: AsyncSession = Depends(get_db)):
    service = CRMService(db)
    return await service.get_ai_stats()
