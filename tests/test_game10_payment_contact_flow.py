from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

from telegram_bot import main as bot_main


def test_handle_contact_phone_in_payment_flow_creates_payment_and_stops(monkeypatch):
    monkeypatch.setattr(bot_main, "_save_contact_field", AsyncMock(return_value=True))
    monkeypatch.setattr(bot_main, "_send_reply_keyboard_remove", AsyncMock())
    monkeypatch.setattr(bot_main, "_show_screen", AsyncMock())
    create_flow_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_run_game10_payment_create_flow", create_flow_mock)

    update = SimpleNamespace(
        message=SimpleNamespace(contact=SimpleNamespace(phone_number="+79990001122")),
        effective_user=SimpleNamespace(id=777),
    )
    context = SimpleNamespace(user_data={bot_main.PAYMENT_CONTACT_FLOW_KEY: True})

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot_main.handle_contact_phone(update, context))

    create_flow_mock.assert_awaited_once_with(update, context)


def test_handle_contact_email_text_in_payment_mode_creates_payment_and_stops(monkeypatch):
    monkeypatch.setattr(bot_main, "_save_contact_field", AsyncMock(return_value=True))
    monkeypatch.setattr(bot_main, "_send_reply_keyboard_remove", AsyncMock())
    monkeypatch.setattr(bot_main, "_show_screen", AsyncMock())
    create_flow_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_run_game10_payment_create_flow", create_flow_mock)

    message = SimpleNamespace(text="test@example.com")
    update = SimpleNamespace(message=message, effective_message=message)
    context = SimpleNamespace(
        user_data={
            bot_main.PAYMENT_CONTACT_FLOW_KEY: True,
            bot_main.PAYMENT_CONTACT_MODE_KEY: "email",
        }
    )

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot_main.handle_contact_email_text(update, context))

    create_flow_mock.assert_awaited_once_with(update, context)


def test_text_fallback_skipped_while_game10_payment_active(monkeypatch):
    message = SimpleNamespace(text="привет")
    update = SimpleNamespace(message=message, effective_message=message)
    context = SimpleNamespace(
        user_data={
            bot_main.PAYMENT_PENDING_ACTION_KEY: "game10_payment",
            bot_main.AI_MODE_KEY: False,
        }
    )
    show_screen_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_screen_mock)

    asyncio.run(bot_main.handle_text_outside_assistant(update, context))

    show_screen_mock.assert_not_called()
