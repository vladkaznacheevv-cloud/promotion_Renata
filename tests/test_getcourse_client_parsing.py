from core.integrations.getcourse.getcourse_client import GetCourseClient
import asyncio


def test_extract_items_reads_info_list(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    client = GetCourseClient()

    payload = {
        "success": True,
        "info": [
            {"id": 101, "title": "Курс 1"},
            {"id": 102, "title": "Курс 2"},
        ],
    }

    items = client._extract_items(payload)
    assert len(items) == 2
    assert items[0]["id"] == 101


def test_extract_export_urls_builds_api_candidates(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("GETCOURSE_BASE_URL", "https://example.getcourse.ru")
    client = GetCourseClient()

    payload = {
        "success": True,
        "info": {
            "export_id": "555",
            "link": "/pl/api/account/export?export_id=555",
        },
    }

    urls = client._extract_export_urls(payload)
    assert "https://example.getcourse.ru/pl/api/account/export?export_id=555" in urls
    assert "https://example.getcourse.ru/pl/api/account/exports/555" in urls


def test_extract_payload_error_from_failed_response(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    client = GetCourseClient()

    payload = {"success": False, "error": "invalid key"}
    assert client._extract_payload_error(payload) == "invalid key"


def test_entity_paths_appends_defaults_when_custom_config_set(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    monkeypatch.setenv(
        "GETCOURSE_ENTITY_PATHS",
        "products:/pl/api/products,courses:/pl/api/courses",
    )
    client = GetCourseClient()
    by_source = dict(client.entity_paths)
    assert by_source["products"] == "/pl/api/products"
    assert by_source["courses"] == "/pl/api/courses"
    assert "deals" in by_source


def test_action_fallbacks_default(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    monkeypatch.delenv("GETCOURSE_ACTION_FALLBACKS", raising=False)
    client = GetCourseClient()
    assert client.action_fallbacks == ("get", "list", None)
    assert client._auth_params("get")["action"] == "get"


def test_action_error_detection():
    assert GetCourseClient._looks_like_action_error("Пустой параметр action")
    assert GetCourseClient._looks_like_action_error("Unknown action")
    assert not GetCourseClient._looks_like_action_error("invalid key")


def test_actions_for_source_include_source_specific_action(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    client = GetCourseClient()
    actions = client._actions_for_source("products", "/pl/api/products")
    assert actions[0] == "products"
    assert "get" in actions


def test_actions_for_account_source_include_action_fallback(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    client = GetCourseClient()
    actions = client._actions_for_source("deals", "/pl/api/account/deals")
    assert "deals" in actions
    assert "get" in actions
    assert "list" in actions
    assert actions[-1] is None


def test_fetch_with_action_falls_back_to_post(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    client = GetCourseClient()

    class _FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return _FakeResponse({"success": False, "error": "Пустой параметр action"})

        async def post(self, *args, **kwargs):
            return _FakeResponse({"items": [{"id": 1, "title": "Тест"}]})

    monkeypatch.setattr("core.integrations.getcourse.getcourse_client.httpx.AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        client._fetch_with_action(
            "https://example.getcourse.ru/pl/api/deals",
            "deals",
            timeout=client_timeout(),
        )
    )
    assert len(result) == 1
    assert result[0]["id"] == 1


def client_timeout():
    import httpx

    return httpx.Timeout(15.0, connect=5.0)


def test_normalize_api_path_rewrites_deals_to_account():
    value = GetCourseClient._normalize_api_path("/pl/api/deals")
    assert value == "/pl/api/account/deals"


def test_parse_csv_items():
    csv_text = "id;title;price\n1;Курс A;1000\n2;Курс B;2000\n"
    rows = GetCourseClient._parse_csv_items(csv_text)
    assert len(rows) == 2
    assert rows[0]["id"] == "1"
    assert rows[0]["title"] == "Курс A"


def test_headers_without_bearer_by_default(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    monkeypatch.delenv("GETCOURSE_USE_BEARER", raising=False)
    client = GetCourseClient()
    headers = client._headers()
    assert "Authorization" not in headers


def test_headers_with_bearer_when_enabled(monkeypatch):
    monkeypatch.setenv("GETCOURSE_ENABLED", "true")
    monkeypatch.setenv("GETCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("GETCOURSE_USE_BEARER", "true")
    client = GetCourseClient()
    headers = client._headers()
    assert headers["Authorization"] == "Bearer test-key"
