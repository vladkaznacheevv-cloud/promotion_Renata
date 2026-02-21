import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from core.integrations.getcourse.getcourse_export_client import ExportResult
from core.integrations.getcourse.getcourse_service import GetCourseService


class _FakeExportClient:
    def __init__(self) -> None:
        self.enabled = True
        self.base_url = "https://example.getcourse.ru"

    async def export_resource(self, resource: str, last_sync_at=None):
        if resource == "transactions":
            return ExportResult(
                items=[],
                fetched=0,
                error="Unsupported resource",
                status_code=404,
                error_kind="unsupported",
            )
        if resource == "payments":
            return ExportResult(items=[], fetched=0, error=None)
        return ExportResult(items=[{"id": "1"}], fetched=1, error=None)


def test_unsupported_resource_is_not_fatal(monkeypatch):
    monkeypatch.setenv("GETCOURSE_USERS_RESOURCES", "users")
    monkeypatch.setenv("GETCOURSE_PAYMENTS_RESOURCES", "payments,transactions")
    monkeypatch.setenv("GETCOURSE_CATALOG_RESOURCES", "deals")

    service = GetCourseService(db=None)  # type: ignore[arg-type]
    service.export_client = _FakeExportClient()  # type: ignore[assignment]
    async def _fake_state():
        return SimpleNamespace(last_sync_at=datetime.now(tz=timezone.utc))

    service._state = _fake_state  # type: ignore[method-assign]

    payload = asyncio.run(
        service.fetch_export_payloads(sync_users=True, sync_payments=True, sync_catalog=True)
    )

    assert payload["fatal_auth_error"] is False
    assert payload["successful_resources"] >= 1
    assert "transactions" in payload["unsupported_resources"]
    assert payload["errors"] == []


def test_busy_is_not_success_but_not_auth_fatal(monkeypatch):
    monkeypatch.setenv("GETCOURSE_USERS_RESOURCES", "users")
    monkeypatch.setenv("GETCOURSE_PAYMENTS_RESOURCES", "payments")
    monkeypatch.setenv("GETCOURSE_CATALOG_RESOURCES", "deals")

    service = GetCourseService(db=None)  # type: ignore[arg-type]

    class _BusyClient:
        enabled = True
        base_url = "https://example.getcourse.ru"

        async def export_resource(self, resource: str, last_sync_at=None):
            if resource == "payments":
                return ExportResult(
                    items=[],
                    fetched=0,
                    error="busy",
                    status_code=200,
                    error_kind="busy",
                    error_code=905,
                )
            return ExportResult(items=[{"id": "1"}], fetched=1, error=None)

    service.export_client = _BusyClient()  # type: ignore[assignment]

    async def _fake_state():
        return SimpleNamespace(last_sync_at=datetime.now(tz=timezone.utc))

    service._state = _fake_state  # type: ignore[method-assign]
    payload = asyncio.run(service.fetch_export_payloads(sync_users=True, sync_payments=True, sync_catalog=False))
    assert payload["fatal_auth_error"] is False
    assert payload["successful_resources"] == 1
    assert "payments" in payload["busy_resources"]
