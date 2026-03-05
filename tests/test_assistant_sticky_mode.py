from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

from telegram_bot import main as bot_main


def _message_update(text: str, user_id: int = 100):
    message = SimpleNamespace(text=text)
    user = SimpleNamespace(id=user_id)
    return SimpleNamespace(
        message=message,
        effective_message=message,
        effective_user=user,
        callback_query=None,
    )


def _callback_update(data: str = "main_menu", user_id: int = 100):
    callback = SimpleNamespace(data=data)
    user = SimpleNamespace(id=user_id)
    return SimpleNamespace(
        callback_query=callback,
        effective_user=user,
        effective_message=None,
        message=None,
    )


def _context(user_data: dict | None = None):
    return SimpleNamespace(user_data=user_data or {})


def test_assistant_timeout_exits_and_shows_menu(monkeypatch):
    context = _context(
        {
            bot_main.AI_MODE_KEY: True,
            bot_main.ASSISTANT_TOPIC_KEY: "game10",
            bot_main.ASSISTANT_LAST_ACTIVITY_TS_KEY: int(time.time()) - 3700,
        }
    )
    update = _message_update("что внутри", user_id=501)

    show_menu_mock = AsyncMock()
    ai_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(bot_main, "_show_main_menu_bottom", show_menu_mock)
    monkeypatch.setattr(bot_main, "_send_ai_response", ai_mock)

    guarded = bot_main._guard_user_handler(bot_main.handle_ai_message, busy_mode="notify")
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(guarded(update, context))

    assert context.user_data.get(bot_main.AI_MODE_KEY) is False
    assert bot_main.ASSISTANT_TOPIC_KEY not in context.user_data
    assert bot_main.ASSISTANT_LAST_ACTIVITY_TS_KEY not in context.user_data
    show_menu_mock.assert_awaited_once()
    ai_mock.assert_not_called()


def test_intro_shown_once_and_ai_reply_without_keyboard(monkeypatch):
    context = _context()
    entry_update = _callback_update(data="ai_chat", user_id=777)

    answer_mock = AsyncMock()
    show_screen_mock = AsyncMock()
    ai_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(bot_main, "_answer", answer_mock)
    monkeypatch.setattr(bot_main, "_show_screen", show_screen_mock)
    monkeypatch.setattr(bot_main, "_send_ai_response", ai_mock)

    asyncio.run(bot_main.show_ai_chat(entry_update, context))

    assert context.user_data.get(bot_main.AI_MODE_KEY) is True
    assert context.user_data.get(bot_main.ASSISTANT_INTRO_SHOWN_KEY) is True
    assert context.user_data.get(bot_main.ASSISTANT_LAST_ACTIVITY_TS_KEY)
    assert show_screen_mock.await_args.kwargs.get("reply_markup") is not None
    assert show_screen_mock.await_args.kwargs.get("parse_mode") is None
    assert show_screen_mock.await_args.kwargs.get("ui_mode") is False

    message_update = _message_update("меню", user_id=777)
    asyncio.run(bot_main.handle_ai_message(message_update, context))

    ai_mock.assert_awaited_once()
    assert "reply_markup" not in ai_mock.await_args.kwargs


def test_menu_button_exits_assistant(monkeypatch):
    context = _context(
        {
            bot_main.AI_MODE_KEY: True,
            bot_main.ASSISTANT_TOPIC_KEY: "course",
            bot_main.ASSISTANT_LAST_ACTIVITY_TS_KEY: int(time.time()),
            bot_main.ASSISTANT_INTRO_SHOWN_KEY: True,
        }
    )
    update = _callback_update(data="main_menu", user_id=901)

    answer_mock = AsyncMock()
    show_menu_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_answer", answer_mock)
    monkeypatch.setattr(bot_main, "_show_main_menu_bottom", show_menu_mock)

    asyncio.run(bot_main.main_menu(update, context))

    assert context.user_data.get(bot_main.AI_MODE_KEY) is False
    assert bot_main.ASSISTANT_TOPIC_KEY not in context.user_data
    assert bot_main.ASSISTANT_LAST_ACTIVITY_TS_KEY not in context.user_data
    assert bot_main.ASSISTANT_INTRO_SHOWN_KEY not in context.user_data
    show_menu_mock.assert_awaited_once()
