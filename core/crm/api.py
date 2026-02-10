from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.auth.deps import require_roles
from core.crm.schemas import (
    AiStatsOut,
    AttendeeCreate,
    AttendeesOut,
    ClientCreate,
    ClientOut,
    ClientUpdate,
    ClientsOut,
    CatalogItemOut,
    CatalogListOut,
    EventCreate,
    EventOut,
    EventUpdate,
    EventsOut,
    GetCourseSummaryOut,
    PaymentCreateIn,
    PaymentOut,
    PaymentUpdateIn,
    PaymentsOut,
    RevenueSummaryOut,
    TgIdRequest,
)
from core.crm.service import CRMService

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"status": "ok"}


@router.get("/clients", response_model=ClientsOut)
async def get_clients(
    limit: int = Query(10, ge=1, le=100),
    stage: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.list_clients(limit=limit, stage=stage, search=search)


@router.post("/clients", response_model=ClientOut)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    return await service.create_client(payload)


@router.patch("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
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
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    ok = await service.delete_client(client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted"}


@router.get("/catalog", response_model=CatalogListOut)
async def get_catalog(
    type: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.list_catalog(
        item_type=type,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/catalog/{item_id}", response_model=CatalogItemOut)
async def get_catalog_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    result = await service.get_catalog_item(item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return result


@router.get("/events", response_model=EventsOut)
async def get_events(
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.list_events(limit=limit, status=status)


@router.get("/events/active")
async def get_active_events(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.list_active_events(limit=limit)


@router.post("/events/{event_id}/signup")
async def signup_event(
    event_id: int,
    payload: TgIdRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    result = await service.add_attendee_by_tg_id(event_id, payload.tg_id)
    if not result.get("ok") and result.get("error") == "event_not_found":
        raise HTTPException(status_code=404, detail="Event not found")
    if not result.get("ok") and result.get("error") == "user_not_found":
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "already": result.get("already", False)}


@router.post("/events/{event_id}/cancel")
async def cancel_event_signup(
    event_id: int,
    payload: TgIdRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    result = await service.remove_attendee_by_tg_id(event_id, payload.tg_id)
    if not result.get("ok") and result.get("error") == "event_not_found":
        raise HTTPException(status_code=404, detail="Event not found")
    if not result.get("ok") and result.get("error") == "user_not_found":
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "removed": result.get("removed", False)}


@router.get("/events/{event_id}/attendees", response_model=AttendeesOut)
async def get_event_attendees(
    event_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    result = await service.list_attendees(event_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/events/{event_id}/attendees")
async def add_event_attendee(
    event_id: int,
    payload: AttendeeCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    if payload.client_id is None and payload.tg_id is None:
        raise HTTPException(status_code=422, detail="client_id or tg_id is required")

    user = None
    if payload.client_id is not None:
        user = await service._get_user(payload.client_id)
    elif payload.tg_id is not None:
        user = await service._get_user_by_tg_id(payload.tg_id)

    if user is None:
        raise HTTPException(status_code=404, detail="Client not found")

    attendee, ok, existed = await service.add_attendee(event_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "exists" if existed else "ok", "attendee": attendee}


@router.delete("/events/{event_id}/attendees/{client_id}")
async def remove_event_attendee(
    event_id: int,
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    ok, removed = await service.remove_attendee(event_id, client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event or client not found")
    if not removed:
        raise HTTPException(status_code=404, detail="Attendee not found")
    return {"status": "deleted"}


@router.post("/events", response_model=EventOut)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    return await service.create_event(payload)


@router.patch("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
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
    _: object = Depends(require_roles("admin", "manager")),
):
    service = CRMService(db)
    ok = await service.delete_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted"}


@router.get("/ai/stats", response_model=AiStatsOut)
async def get_ai_stats(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.get_ai_stats()


@router.get("/payments", response_model=PaymentsOut)
async def get_payments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int | None = Query(None),
    event_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.list_payments(
        limit=limit,
        offset=offset,
        user_id=user_id,
        event_id=event_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/payments", response_model=PaymentOut)
async def create_payment(
    payload: PaymentCreateIn,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager")),
):
    if payload.user_id is None and payload.tg_id is None:
        raise HTTPException(status_code=422, detail="user_id or tg_id is required")
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be > 0")
    service = CRMService(db)
    result = await service.create_payment_for_user(
        user_id=payload.user_id,
        tg_id=payload.tg_id,
        event_id=payload.event_id,
        amount=payload.amount,
        currency=payload.currency or "RUB",
        source=payload.source,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="User or event not found")
    return result


@router.patch("/payments/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: int,
    payload: PaymentUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin")),
):
    if payload.status not in {"pending", "paid", "failed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid status")
    service = CRMService(db)
    result = await service.mark_payment_status(payment_id, payload.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return result


@router.get("/revenue/summary", response_model=RevenueSummaryOut)
async def get_revenue_summary(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.get_revenue_summary()


@router.get("/integrations/getcourse/summary", response_model=GetCourseSummaryOut)
async def get_getcourse_summary(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    service = CRMService(db)
    return await service.get_getcourse_summary()


@router.post("/integrations/getcourse/sync", response_model=GetCourseSummaryOut)
async def sync_getcourse(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("admin")),
):
    service = CRMService(db)
    return await service.sync_getcourse()
