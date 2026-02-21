from datetime import datetime, timezone

from core.integrations.getcourse.getcourse_export_client import GetCourseExportClient


def test_export_filters_are_added_when_missing(monkeypatch):
    monkeypatch.setenv("GETCOURSE_EXPORT_FROM_DAYS", "30")
    filters = GetCourseExportClient.build_filters(filters={})
    assert "created_at[from]" in filters


def test_export_filters_use_last_sync_when_available():
    last_sync = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
    filters = GetCourseExportClient.build_filters(last_sync_at=last_sync)
    assert filters["created_at[from]"] == "2026-02-13"


def test_export_filters_keep_existing_filter():
    filters = GetCourseExportClient.build_filters(filters={"created_at[from]": "2026-01-01"})
    assert filters["created_at[from]"] == "2026-01-01"
