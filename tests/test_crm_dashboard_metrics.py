import asyncio
from datetime import datetime, timedelta, timezone

from core.crm.service import CRMService


def test_dashboard_bounds_respect_days_window():
    now = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
    start_ts, end_ts = CRMService._dashboard_bounds(7, now_utc=now)

    assert end_ts == now
    assert end_ts - start_ts == timedelta(days=7)


def test_dashboard_summary_uses_paid_and_succeeded_with_paid_timestamp():
    class _FakeDB:
        def __init__(self):
            self.scalar_calls = []

        async def scalar(self, query):
            self.scalar_calls.append(query)
            call_no = len(self.scalar_calls)

            if call_no == 3 or call_no == 4:
                sql = str(query).lower()
                assert "payments.paid_at" in sql
                assert "payments.updated_at" in sql
                assert "payments.created_at" in sql
                params = query.compile().params
                values = []
                for value in params.values():
                    if isinstance(value, (list, tuple, set)):
                        values.extend(str(item).lower() for item in value)
                    else:
                        values.append(str(value).lower())
                assert "paid" in values
                assert "succeeded" in values

            if call_no == 1:
                return 9
            if call_no == 2:
                return 4
            if call_no == 3:
                return 3
            if call_no == 4:
                return 15000
            return 0

    fake_db = _FakeDB()
    service = CRMService(fake_db)  # type: ignore[arg-type]

    result = asyncio.run(service.get_dashboard_summary(days=30))

    assert result["days"] == 30
    assert result["ai_answers"] == 9
    assert result["new_clients"] == 4
    assert result["payments_count"] == 3
    assert result["revenue_total"] == 15000
