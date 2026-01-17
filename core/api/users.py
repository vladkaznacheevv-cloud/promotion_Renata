from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.api.deps import get_db, get_current_user
from core.users.models import User
from core.users.schemas import UserCreate, UserUpdate, UserResponse
from core.users.service import UserService

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def get_users(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    is_vip: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить всех пользователей с фильтрацией"""
    service = UserService(db)
    
    users = await service.get_all(limit=limit, offset=offset)
    
    # Фильтрация на уровне Python (можно оптимизировать)
    if status:
        users = [u for u in users if u.status == status]
    if is_vip is not None:
        users = [u for u in users if u.is_vip == is_vip]
    
    return users


@router.get("/count")
async def get_users_count(db: AsyncSession = Depends(get_db)):
    """Количество пользователей"""
    result = await db.execute(select(func.count(User.id)))
    return {"count": result.scalar()}


@router.get("/vip", response_model=List[UserResponse])
async def get_vip_users(db: AsyncSession = Depends(get_db)):
    """Получить VIP пользователей"""
    service = UserService(db)
    return await service.get_vip_users()


@router.get("/{tg_id}", response_model=UserResponse)
async def get_user(tg_id: int, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по TG ID"""
    service = UserService(db)
    user = await service.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать или обновить пользователя"""
    service = UserService(db)
    return await service.get_or_create(user_data)


@router.patch("/{tg_id}", response_model=UserResponse)
async def update_user(
    tg_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить данные пользователя"""
    service = UserService(db)
    user = await service.update(tg_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.post("/{tg_id}/vip")
async def make_vip(
    tg_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Сделать пользователя VIP"""
    service = UserService(db)
    user = await service.make_vip(tg_id, days=days)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"message": "Пользователь стал VIP", "vip_until": user.vip_until}