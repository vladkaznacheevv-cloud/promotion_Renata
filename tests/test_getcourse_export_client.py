import asyncio

from core.integrations.getcourse.getcourse_export_client import GetCourseExportClient


def test_safe_url_hides_key():
    url = "https://example.getcourse.ru/pl/api/account/users?key=secret&action=export"
    safe = GetCourseExportClient._safe_url(url)
    assert "secret" not in safe
    assert "key=%2A%2A%2A" in safe or "key=***" in safe


def test_export_resource_disabled(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "false")
    monkeypatch.delenv("GETCOURSE_API_KEY", raising=False)
    client = GetCourseExportClient()
    result = asyncio.run(client.export_resource("users"))
    assert result.fetched == 0
    assert result.items == []
    assert result.error


def test_ping_export_busy_905(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "x" * 32)
    monkeypatch.setenv("GETCOURSE_BASE_URL", "https://example.getcourse.ru")

    class _Resp:
        status_code = 200
        text = '{"success":false,"error_code":905,"error":"Уже запущен один экспорт"}'

        def json(self):
            return {
                "success": False,
                "error_code": 905,
                "error": "Уже запущен один экспорт",
            }

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr("core.integrations.getcourse.getcourse_export_client.httpx.AsyncClient", _AsyncClient)
    client = GetCourseExportClient()
    result = asyncio.run(client.ping_export("users"))
    assert result["ok"] is False
    assert result["error_kind"] == "busy"
    assert result["error_code"] == 905
