from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

from telegram_bot import main as bot_main


def _fake_text_update(text: str):
    message = SimpleNamespace(text=text)
    return SimpleNamespace(message=message, effective_message=message)


def _fake_context(user_data: dict | None = None):
    return SimpleNamespace(user_data=user_data or {})


def test_navigation_handler_routes_and_stops_chain(monkeypatch):
    update = _fake_text_update("меню")
    context = _fake_context()
    route_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(bot_main, "_route_detected_intent", route_mock)

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot_main.handle_navigation_text_message(update, context))

    route_mock.assert_awaited_once_with(update, context, "MENU")


def test_ai_handler_does_not_call_ai_for_navigation_text(monkeypatch):
    update = _fake_text_update("главное меню")
    context = _fake_context({bot_main.AI_MODE_KEY: True})
    ai_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_send_ai_response", ai_mock)

    asyncio.run(bot_main.handle_ai_message(update, context))

    ai_mock.assert_not_called()


def test_no_ai_outside_assistant(monkeypatch):
    update = _fake_text_update("расскажи подробнее")
    context = _fake_context({bot_main.AI_MODE_KEY: False})
    ai_mock = AsyncMock()
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_send_ai_response", ai_mock)
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)

    asyncio.run(bot_main.handle_text_outside_assistant(update, context))

    ai_mock.assert_not_called()
    assert show_mock.await_count == 1
    assert bot_main.ASSISTANT_ENTRY_HINT_TEXT in show_mock.await_args.args


def test_ai_only_in_assistant_mode_with_focus(monkeypatch):
    update = _fake_text_update("что внутри программы")
    context = _fake_context(
        {
            bot_main.AI_MODE_KEY: True,
            bot_main.PRODUCT_FOCUS_KEY: "game10",
        }
    )
    ai_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(bot_main, "_send_ai_response", ai_mock)

    asyncio.run(bot_main.handle_ai_message(update, context))

    ai_mock.assert_awaited_once()
    assert ai_mock.await_args.kwargs["response_mode"] == "assistant"


def test_build_ai_request_message_includes_focus_for_game10():
    context = _fake_context({bot_main.PRODUCT_FOCUS_KEY: "game10"})
    payload = bot_main._build_ai_request_message(context, "что внутри")
    assert payload.startswith("[FOCUS:GAME10]")
