from __future__ import annotations

from core.integrations.getcourse.url_utils import normalize_getcourse_url


def test_normalize_url_accepts_valid_http_url():
    url, reason = normalize_getcourse_url("https://example.getcourse.ru/pl/cms/page/view?key=abcdefgh")
    assert url == "https://example.getcourse.ru/pl/cms/page/view?key=abcdefgh"
    assert reason is None


def test_normalize_url_removes_control_chars():
    url, reason = normalize_getcourse_url(" https://example.getcourse.ru/pl/cms/page/view?key=abcdefgh\t\n")
    assert url == "https://example.getcourse.ru/pl/cms/page/view?key=abcdefgh"
    assert reason is None


def test_normalize_url_rejects_short_query_key():
    url, reason = normalize_getcourse_url("https://example.getcourse.ru/pl/cms/page/view?key=abc")
    assert url is None
    assert reason == "truncated_key"
