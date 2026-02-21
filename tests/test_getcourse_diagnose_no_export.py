import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from core.integrations.getcourse.getcourse_service import GetCourseService


class _ProbeOnlyClient:
    def __init__(self):
        self.enabled = True
        self.base_url = "https://example.getcourse.ru"

    async def ping_export(self, resource: str):  # pragma: no cover - must never be called by diagnose
        raise AssertionError("diagnose must not call ping_export")

    async def export_resource(self, *args, **kwargs):  # pragma: no cover - must never be called by diagnose
        raise AssertionError("diagnose must not call export_resource")


def test_diagnose_uses_probe_not_export(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "x" * 32)
    monkeypatch.setenv("GETCOURSE_USERS_RESOURCES", "users")
    monkeypatch.setenv("GETCOURSE_PAYMENTS_RESOURCES", "payments,transactions")
    monkeypatch.setenv("GETCOURSE_CATALOG_RESOURCES", "deals")

    service = GetCourseService(db=None)  # type: ignore[arg-type]
    service.export_client = _ProbeOnlyClient()  # type: ignore[assignment]

    async def _fake_state():
        return SimpleNamespace(last_sync_at=datetime.now(tz=timezone.utc))

    service._state = _fake_state  # type: ignore[method-assign]
    payload = asyncio.run(service.diagnose_resources())
    assert payload["enabled"] is True
    assert payload["fatalAuthError"] is False
    assert payload["unsupportedResources"] == []
    assert "users" in payload["successfulResources"]
    assert "transactions" in payload["successfulResources"]
