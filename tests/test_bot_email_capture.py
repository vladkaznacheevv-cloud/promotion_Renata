from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

from telegram_bot import main as bot_main


def test_waiting_email_saves_and_confirms(monkeypatch):
    save_mock = AsyncMock(return_value=True)
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_save_contact_field", save_mock)
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)
    monkeypatch.setattr(
        bot_main,
        "_get_contact_snapshot",
        AsyncMock(return_value={"id": 1, "phone": "+79991234567", "email": None}),
    )

    update = SimpleNamespace(
        message=SimpleNamespace(text="test@example.com"),
        effective_user=SimpleNamespace(id=123),
    )
    context = SimpleNamespace(
        user_data={
            bot_main.WAITING_CONTACT_EMAIL_KEY: True,
            bot_main.WAITING_CONTACT_PHONE_KEY: False,
            bot_main.CONTACT_PHONE_KEY: "+79991234567",
        }
    )

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot_main.handle_contact_email_text(update, context))

    save_mock.assert_awaited_once_with(update, context, email="test@example.com")
    assert context.user_data.get(bot_main.WAITING_CONTACT_EMAIL_KEY) is False
    shown_text = str(show_mock.await_args.args[2])
    assert "Email сохранён" in shown_text


def test_waiting_email_db_error_keeps_state_and_replies(monkeypatch):
    monkeypatch.setattr(bot_main, "_save_contact_field", AsyncMock(return_value=False))
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)
    monkeypatch.setattr(
        bot_main,
        "_get_contact_snapshot",
        AsyncMock(return_value={"id": 1, "phone": "+79991234567", "email": None}),
    )

    update = SimpleNamespace(
        message=SimpleNamespace(text="test@example.com"),
        effective_user=SimpleNamespace(id=123),
    )
    context = SimpleNamespace(
        user_data={
            bot_main.WAITING_CONTACT_EMAIL_KEY: True,
            bot_main.CONTACT_PHONE_KEY: "+79991234567",
        }
    )

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot_main.handle_contact_email_text(update, context))

    assert context.user_data.get(bot_main.WAITING_CONTACT_EMAIL_KEY) is True
    shown_text = str(show_mock.await_args.args[2])
    assert "Не удалось сохранить email" in shown_text
