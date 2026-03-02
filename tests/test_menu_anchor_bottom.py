from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot.screen_manager import ScreenManager


def _menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data="main_menu")]])


def test_show_main_menu_bottom_always_sends_message_and_updates_anchor():
    callback_query = SimpleNamespace(answer=AsyncMock())
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=321)),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        callback_query=callback_query,
        message=None,
    )
    context = SimpleNamespace(
        bot=bot,
        user_data={ScreenManager.MENU_ANCHOR_MESSAGE_ID_KEY: 100},
    )

    asyncio.run(
        ScreenManager().show_main_menu_bottom(
            update,
            context,
            "Главное меню",
            reply_markup=_menu_markup(),
        )
    )

    callback_query.answer.assert_awaited_once()
    bot.send_message.assert_awaited_once()
    bot.edit_message_text.assert_not_called()
    assert bot.send_message.await_args.kwargs.get("parse_mode") is None
    assert context.user_data[ScreenManager.MENU_ANCHOR_MESSAGE_ID_KEY] == 321


def test_update_main_menu_anchor_edits_existing_anchor():
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=500)),
        edit_message_text=AsyncMock(return_value=None),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        callback_query=None,
        message=SimpleNamespace(text="nav"),
    )
    context = SimpleNamespace(
        bot=bot,
        user_data={ScreenManager.MENU_ANCHOR_MESSAGE_ID_KEY: 222},
    )

    asyncio.run(
        ScreenManager().update_main_menu_anchor(
            update,
            context,
            "Главное меню",
            reply_markup=_menu_markup(),
            parse_mode=None,
        )
    )

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_called()


def test_regular_navigation_uses_edit_by_menu_anchor():
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=500)),
        edit_message_text=AsyncMock(return_value=None),
        delete_message=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        callback_query=None,
        message=SimpleNamespace(text="каталог"),
    )
    context = SimpleNamespace(
        bot=bot,
        user_data={ScreenManager.MENU_ANCHOR_MESSAGE_ID_KEY: 444},
    )

    asyncio.run(
        ScreenManager().show_screen(
            update,
            context,
            "Экран каталога",
            reply_markup=_menu_markup(),
            ui_mode=True,
        )
    )

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_called()
