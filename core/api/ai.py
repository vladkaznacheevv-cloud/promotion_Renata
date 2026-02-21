from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.deps import get_db
from core.ai.ai_service import AIService
from core.auth.deps import require_roles
from core.users.service import UserService

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    tg_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    history: List[dict]


class AiPingResponse(BaseModel):
    ok: bool
    model: str
    reply: str


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
    
    response, new_history = await ai.chat(request.message, history, tg_id=request.tg_id)
    
    return ChatResponse(response=response, history=new_history)


@router.post("/chat/{tg_id}", response_model=ChatResponse)
async def chat_with_user(
    tg_id: int,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI чат с конкретным пользователем"""
    ai = AIService()
    
    response, new_history = await ai.chat(request.message, tg_id=tg_id)

    return ChatResponse(response=response, history=new_history)


@router.get("/ping", response_model=AiPingResponse)
async def ping_ai(
    _: object = Depends(require_roles("admin", "manager", "viewer")),
):
    ai = AIService()
    ok, reply = await ai.ping()
    if not ok:
        raise HTTPException(status_code=502, detail={"ok": False, "reason": reply})
    return AiPingResponse(ok=True, model=ai.model, reply=reply)
