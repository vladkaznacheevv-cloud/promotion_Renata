import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from core.crm.service import CRMService


class _FakeIntegration:
    enabled = True
    base_url = "https://example.getcourse.ru"

    def __init__(self):
        self.saved_error = None

    async def _state(self):
        return SimpleNamespace(last_sync_at=datetime(2026, 2, 1, tzinfo=timezone.utc))

    async def fetch_export_payloads(self, **kwargs):
        return {
            "users": [{"id": "1", "email": "u@example.com"}],
            "payments": [],
            "catalog": [],
            "counts": {"users": 1, "payments": 0},
            "errors": ["payments: busy"],
            "unsupported_resources": [],
            "resource_statuses": {},
            "busy_resources": ["payments"],
            "fatal_auth_error": False,
            "successful_resources": 1,
        }

    async def save_sync_result(self, **kwargs):
        self.saved_error = kwargs.get("error")

    async def summary(self):
        return {
            "enabled": True,
            "status": "OK" if not self.saved_error else "ERROR",
            "ok": self.saved_error is None,
            "lastError": self.saved_error,
            "unsupportedResources": [],
        }


def test_sync_busy_not_fatal_with_success(monkeypatch):
    class _FakeDB:
        async def flush(self):
            return None

    service = CRMService(db=_FakeDB())  # type: ignore[arg-type]
    integration = _FakeIntegration()

    monkeypatch.setattr(service, "get_getcourse_integration", lambda: integration)
    monkeypatch.setattr(service, "_get_sync_cooldown_minutes", lambda: 0)

    async def _lock_true():
        return True

    async def _lock_release():
        return None

    async def _upsert_client(_payload):
        return "created"

    monkeypatch.setattr(service, "_try_acquire_getcourse_sync_lock", _lock_true)
    monkeypatch.setattr(service, "_release_getcourse_sync_lock", _lock_release)
    monkeypatch.setattr(service, "upsert_client_from_getcourse", _upsert_client)

    result = asyncio.run(service.sync_getcourse(force=True, actor_role="admin"))
    assert result["ok"] is True
    assert result["status"] == "OK"
