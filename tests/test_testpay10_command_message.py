from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram_bot import main as bot_main


def test_testpay10_command_sends_plain_text_with_parse_mode_none(monkeypatch):
    monkeypatch.setattr(bot_main, "PAYMENTS_TEST_ENABLED", True)
    monkeypatch.setattr(bot_main, "_is_admin_user_id", lambda user_id: True)
    monkeypatch.setattr(
        bot_main,
        "_create_test_payment_backend",
        AsyncMock(
            return_value={
                "ok": True,
                "payment_id": "yk_test_1",
                "confirmation_url": "https://pay.example.com/confirm?payment=1",
            }
        ),
    )
    monkeypatch.setattr(bot_main, "_reply", AsyncMock())

    send_mock = AsyncMock()
    context = SimpleNamespace(bot=SimpleNamespace(send_message=send_mock))
    update = SimpleNamespace(
        effective_message=SimpleNamespace(),
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=777),
    )

    asyncio.run(bot_main.testpay10_command(update, context))

    assert send_mock.await_count >= 1
    kwargs = send_mock.await_args.kwargs
    assert kwargs["chat_id"] == 777
    assert kwargs.get("parse_mode", "missing") is None
    assert kwargs.get("disable_web_page_preview") is True
    text = str(kwargs.get("text") or "")
    assert "https://pay.example.com/confirm?payment=1" in text
    assert "`" not in text
    assert "<" not in text
    assert ">" not in text
