import asyncio
import os
import sys

from sqlalchemy import func, select

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.models  # noqa: F401
import core.db.database as db
from core.crm.models import CRMUserActivity
from core.crm.service import CRMService
from core.users.models import User


def _batch_size() -> int:
    raw = (os.getenv("CRM_STAGE_BACKFILL_BATCH_SIZE") or "").strip()
    try:
        value = int(raw) if raw else 200
    except Exception:
        value = 200
    return max(1, min(value, 5000))


async def _recompute_all_clients(*, session, batch_size: int) -> dict[str, int]:
    service = CRMService(session)
    cursor = 0
    checked = 0
    updated = 0

    while True:
        rows = await session.execute(
            select(User, func.coalesce(CRMUserActivity.ai_chats, 0))
            .outerjoin(CRMUserActivity, CRMUserActivity.user_id == User.id)
            .where(User.id > int(cursor))
            .order_by(User.id.asc())
            .limit(batch_size)
        )
        items = rows.all()
        if not items:
            break

        for user, ai_chats_count in items:
            checked += 1
            changed = await service.recompute_stage_for_user(
                user,
                ai_chats_count=int(ai_chats_count or 0),
                reason="backfill_recompute",
            )
            if changed:
                updated += 1
            cursor = int(user.id)

        await session.commit()

    return {"checked": checked, "updated": updated}


async def main() -> None:
    batch_size = _batch_size()
    db.init_db()
    assert db.async_session is not None

    async with db.async_session() as session:
        service = CRMService(session)

        backfill_stats = await service.backfill_last_payment_at(batch_size=batch_size)
        await session.commit()

        recompute_stats = await _recompute_all_clients(session=session, batch_size=batch_size)

    print(
        "[backfill_recompute_stage] done "
        f"backfill_checked={backfill_stats['checked']} "
        f"backfill_updated={backfill_stats['updated']} "
        f"recompute_checked={recompute_stats['checked']} "
        f"recompute_updated={recompute_stats['updated']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
