from core.crm.service import CRMService
from core.users.models import User
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock


def test_stage_new_to_engaged_on_message():
    assert CRMService.stage_after_message(User.CRM_STAGE_NEW) == User.CRM_STAGE_ENGAGED


def test_contacts_set_ready_to_pay():
    assert CRMService.stage_after_contacts(User.CRM_STAGE_ENGAGED) == User.CRM_STAGE_READY_TO_PAY


def test_payment_paid_sets_paid_stage():
    assert CRMService.stage_after_payment_paid(User.CRM_STAGE_READY_TO_PAY) == User.CRM_STAGE_PAID


def _user_stub(*, last_activity_at=None, last_payment_at=None):
    return SimpleNamespace(
        crm_stage=User.CRM_STAGE_NEW,
        last_activity_at=last_activity_at,
        last_payment_at=last_payment_at,
    )


def test_compute_stage_new_without_ai_and_recent_activity():
    now = datetime.now(timezone.utc)
    user = _user_stub(last_activity_at=now - timedelta(days=1))
    stage, reason = CRMService.compute_stage(user, ai_chats_count=0, now_utc=now)
    assert stage == User.CRM_STAGE_NEW
    assert reason == "new_client"


def test_compute_stage_engaged_with_ai_activity():
    now = datetime.now(timezone.utc)
    user = _user_stub(last_activity_at=now - timedelta(days=1))
    stage, reason = CRMService.compute_stage(user, ai_chats_count=2, now_utc=now)
    assert stage == User.CRM_STAGE_ENGAGED
    assert reason == "ai_activity_detected"


def test_compute_stage_inactive_after_7_days_without_payment():
    now = datetime.now(timezone.utc)
    user = _user_stub(last_activity_at=now - timedelta(days=8))
    stage, reason = CRMService.compute_stage(user, ai_chats_count=5, now_utc=now)
    assert stage == User.CRM_STAGE_INACTIVE
    assert reason == "inactive_7d"


def test_compute_stage_paid_when_recent_payment_exists():
    now = datetime.now(timezone.utc)
    user = _user_stub(last_activity_at=now - timedelta(days=20), last_payment_at=now - timedelta(days=1))
    stage, reason = CRMService.compute_stage(user, ai_chats_count=0, now_utc=now)
    assert stage == User.CRM_STAGE_PAID
    assert reason == "payment_recent"


def test_compute_stage_hot_after_7_days_from_payment():
    now = datetime.now(timezone.utc)
    user = _user_stub(last_activity_at=now - timedelta(days=20), last_payment_at=now - timedelta(days=8))
    stage, reason = CRMService.compute_stage(user, ai_chats_count=0, now_utc=now)
    assert stage == User.CRM_STAGE_MANAGER_FOLLOWUP
    assert reason == "payment_older_than_7d"


def test_list_clients_applies_limit_and_offset():
    class _FakeResult:
        def scalars(self):
            return SimpleNamespace(all=lambda: [])

    class _FakeDB:
        def __init__(self):
            self.query = None

        async def scalar(self, _query):
            return 0

        async def execute(self, query):
            self.query = query
            return _FakeResult()

    fake_db = _FakeDB()
    service = CRMService(fake_db)  # type: ignore[arg-type]
    service._build_client_items = AsyncMock(return_value=[])

    result = asyncio.run(service.list_clients(limit=25, offset=50))

    assert result == {"items": [], "total": 0}
    assert fake_db.query is not None
    assert getattr(fake_db.query._limit_clause, "value", None) == 25
    assert getattr(fake_db.query._offset_clause, "value", None) == 50
