from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.ai.ai_service import AIService
from core.users.service import UserService
from core.users.models import User

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    tg_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    history: List[dict]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI чат с пользователем"""
    ai = AIService()
    
    # Получаем историю из сервиса
    history = []
    if request.tg_id:
        user_service = UserService(db)
        user = await user_service.get_by_tg_id(request.tg_id)
        if user:
            # Можно загружать историю из Redis
            pass
    
    response, new_history = await ai.chat(request.message, history)
    
    return ChatResponse(response=response, history=new_history)


@router.post("/chat/{tg_id}", response_model=ChatResponse)
async def chat_with_user(
    tg_id: int,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI чат с конкретным пользователем"""
    ai = AIService()
    
    response, new_history = await ai.chat(request.message)
    
    # Логируем в БД
    user_service = UserService(db)
    await user_service.log_event(
        user_tg_id=tg_id,
        event_type="ai_chat",
        event_data={"message": request.message, "response": response},
        description="AI чат через API"
    )
    
    return ChatResponse(response=response, history=new_history)