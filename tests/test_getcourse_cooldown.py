from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

pytest.importorskip("jose")

from core.api.deps import get_db
from core.auth.deps import get_current_admin_user
from core.crm.api import router as crm_router
from core.crm.service import CRMService, GetCourseSyncCooldownError


async def _override_db():
    yield None


async def _override_user():
    return SimpleNamespace(id=1, role="admin", is_active=True)


def _build_app():
    app = FastAPI()
    app.include_router(crm_router, prefix="/api/crm")
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_admin_user] = _override_user
    return app


def test_sync_cooldown_and_force(monkeypatch):
    next_at = datetime.now(tz=timezone.utc) + timedelta(hours=6)
    calls = {"count": 0}

    async def _sync(self, *, sync_users=True, sync_payments=True, sync_catalog=True, force=False, actor_role=None):
        calls["count"] += 1
        if calls["count"] == 2 and not force:
            raise GetCourseSyncCooldownError(next_allowed_at=next_at, cooldown_minutes=360)
        return {
            "enabled": True,
            "status": "OK",
            "lastSyncAt": datetime.now(tz=timezone.utc).isoformat(),
            "counts": {},
        }

    monkeypatch.setattr(CRMService, "sync_getcourse", _sync)

    client = TestClient(_build_app())

    first = client.post("/api/crm/integrations/getcourse/sync")
    assert first.status_code == 200

    second = client.post("/api/crm/integrations/getcourse/sync")
    assert second.status_code == 429
    body = second.json()
    assert body["detail"]["detail"] == "Sync cooldown active"
    assert body["detail"]["cooldownMinutes"] == 360
    assert "nextAllowedAt" in body["detail"]

    forced = client.post("/api/crm/integrations/getcourse/sync?force=true")
    assert forced.status_code == 200

