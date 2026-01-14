from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import User

router = APIRouter()

@router.get("/users")
async def get_users(session: AsyncSession = Depends(get_async_session)):
    users = await session.execute(select(User))
    return users.scalars().all()

@router.post("/users")
async def create_user(user_data: dict, session: AsyncSession = Depends(get_async_session)):
    user = User(
        tg_id=user_data['tg_id'],
        first_name=user_data.get('first_name', ''),
        last_name=user_data.get('last_name', ''),
        username=user_data.get('username', '')
    )
    session.add(user)
    await session.commit()
    return {"status": "created", "user_id": user.id}