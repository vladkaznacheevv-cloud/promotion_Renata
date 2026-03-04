from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from core.api import payments as payments_api


def test_internal_recheck_calls_yookassa_configuration(monkeypatch):
    configure_mock = Mock()
    fake_yookassa = SimpleNamespace(
        Configuration=SimpleNamespace(configure=configure_mock)
    )
    monkeypatch.setitem(sys.modules, "yookassa", fake_yookassa)
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")
    monkeypatch.setattr(payments_api, "_YOOKASSA_CONFIGURED", False)
    monkeypatch.setattr(
        payments_api,
        "_get_yookassa_payment_status",
        AsyncMock(return_value="pending"),
    )

    payment_obj = SimpleNamespace(
        payment_id="yk_recheck_1",
        tg_id=123456,
        status="pending",
        paid_at=None,
    )

    class _ScalarPaymentResult:
        def scalar_one_or_none(self):
            return payment_obj

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _ScalarPaymentResult()

        async def flush(self):
            return None

    result = asyncio.run(
        payments_api._recheck_yookassa_payment_internal(
            db=_FakeDB(),
            payment_id="yk_recheck_1",
        )
    )

    assert result["status"] == "pending"
    configure_mock.assert_called_once()
