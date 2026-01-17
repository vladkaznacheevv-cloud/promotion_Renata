from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.consultations.models import Consultation
from core.consultations.schemas import ConsultationCreate, ConsultationResponse
from core.consultations.service import ConsultationService

router = APIRouter()


@router.get("/", response_model=List[ConsultationResponse])
async def get_consultations(
    consultation_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить консультации"""
    service = ConsultationService(db)
    consultations = await service.get_active()
    
    if consultation_type:
        consultations = [c for c in consultations if c.type == consultation_type]
    
    return consultations


@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(consultation_id: int, db: AsyncSession = Depends(get_db)):
    """Получить консультацию по ID"""
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Консультация не найдена")
    return consultation


@router.post("/", response_model=ConsultationResponse)
async def create_consultation(
    data: ConsultationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать консультацию"""
    service = ConsultationService(db)
    return await service.create(data)