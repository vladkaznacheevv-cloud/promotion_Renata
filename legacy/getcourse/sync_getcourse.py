import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.db.database as db
from core.crm.service import (
    CRMService,
    GetCourseSyncAlreadyRunningError,
    GetCourseSyncCooldownError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GetCourse sync")
    parser.add_argument("--sync-users", dest="sync_users", action="store_true", default=True)
    parser.add_argument("--no-sync-users", dest="sync_users", action="store_false")
    parser.add_argument("--sync-payments", dest="sync_payments", action="store_true", default=True)
    parser.add_argument("--no-sync-payments", dest="sync_payments", action="store_false")
    parser.add_argument("--sync-catalog", dest="sync_catalog", action="store_true", default=True)
    parser.add_argument("--no-sync-catalog", dest="sync_catalog", action="store_false")
    parser.add_argument("--force", action="store_true", default=False)
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    started_at = datetime.now(tz=timezone.utc)
    db.init_db()
    if db.async_session is None:
        print(json.dumps({"event": "sync_getcourse", "ok": False, "error": "DB session is not initialized"}))
        return 2

    async with db.async_session() as session:
        service = CRMService(session)
        try:
            summary = await service.sync_getcourse(
                sync_users=args.sync_users,
                sync_payments=args.sync_payments,
                sync_catalog=args.sync_catalog,
                force=args.force,
                actor_role="admin",
            )
            await session.commit()
            print(
                json.dumps(
                    {
                        "event": "sync_getcourse",
                        "ok": bool(summary.get("ok", True)),
                        "status": summary.get("status"),
                        "startedAt": started_at.isoformat(),
                        "finishedAt": datetime.now(tz=timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                )
            )
            return 0 if bool(summary.get("ok", True)) else 1
        except GetCourseSyncCooldownError as exc:
            await session.rollback()
            print(
                json.dumps(
                    {
                        "event": "sync_getcourse",
                        "ok": False,
                        "detail": "Sync cooldown active",
                        "nextAllowedAt": exc.next_allowed_at.isoformat(),
                        "cooldownMinutes": exc.cooldown_minutes,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        except GetCourseSyncAlreadyRunningError:
            await session.rollback()
            print(json.dumps({"event": "sync_getcourse", "ok": False, "detail": "Sync already running"}))
            return 0
        except Exception as exc:
            await session.rollback()
            print(json.dumps({"event": "sync_getcourse", "ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
