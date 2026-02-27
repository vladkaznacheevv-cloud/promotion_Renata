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
