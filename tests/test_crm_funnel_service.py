from core.crm.service import CRMService
from core.users.models import User
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


def test_stage_new_to_engaged_on_message():
    assert CRMService.stage_after_message(User.CRM_STAGE_NEW) == User.CRM_STAGE_ENGAGED


def test_contacts_set_ready_to_pay():
    assert CRMService.stage_after_contacts(User.CRM_STAGE_ENGAGED) == User.CRM_STAGE_READY_TO_PAY


def test_payment_paid_sets_paid_stage():
    assert CRMService.stage_after_payment_paid(User.CRM_STAGE_READY_TO_PAY) == User.CRM_STAGE_PAID


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
