import asyncio
from decimal import Decimal

from sqlalchemy import select, func

from core.db import database as db
from core.models import Base
from core.users.models import User
from core.events.models import Event


async def main():
    db.init_db()
    assert db.engine is not None
    assert db.async_session is not None

    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with db.async_session() as session:
        user_count = await session.scalar(select(func.count(User.id)))
        event_count = await session.scalar(select(func.count(Event.id)))

        if (user_count or 0) == 0 and (event_count or 0) == 0:
            event1 = Event(
                title="Концерт \"Ностальгия\"",
                description="Вечер хитов 90-х и 2000-х",
                location="Клуб \"Метро\"",
                is_active=True,
                price=Decimal("1000.00"),
            )
            event2 = Event(
                title="Мастер-класс по SMM",
                description="Онлайн обучение продвижению",
                location="Онлайн",
                is_active=True,
                price=Decimal("0.00"),
            )
            session.add_all([event1, event2])
            await session.flush()

            user1 = User(
                tg_id=10001,
                first_name="Анна",
                last_name="Петрова",
                username="anna_p",
                is_vip=True,
                status=User.STATUS_VIP,
                interested_event_id=event1.id,
            )
            user2 = User(
                tg_id=10002,
                first_name="Михаил",
                last_name="Сидоров",
                username="mike_sid",
                status=User.STATUS_IN_WORK,
                interested_event_id=event2.id,
            )
            session.add_all([user1, user2])

            await session.commit()
            print("Seed complete: 2 events, 2 users")
        else:
            print("Seed skipped: data already exists")


if __name__ == "__main__":
    asyncio.run(main())
