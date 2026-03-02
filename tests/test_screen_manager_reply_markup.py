from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.error import TimedOut

from telegram_bot import main as bot_main
from telegram_bot.screen_manager import ScreenManager


def _build_update(*, callback_query=None):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123456),
        callback_query=callback_query,
        message=None,
    )


def _build_context(bot, *, last_message_id: int):
    return SimpleNamespace(
        bot=bot,
        user_data={ScreenManager.LAST_SCREEN_MESSAGE_ID_KEY: last_message_id},
    )


def test_show_screen_uses_send_message_for_reply_keyboard_on_callback():
    callback_query = SimpleNamespace(answer=AsyncMock())
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=200)),
        edit_message_text=AsyncMock(),
        delete_message=AsyncMock(),
    )
    update = _build_update(callback_query=callback_query)
    context = _build_context(bot, last_message_id=100)
    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton("Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    asyncio.run(
        ScreenManager().show_screen(
            update,
            context,
            "Тест",
            reply_markup=reply_markup,
            prefer_new_on_message=False,
        )
    )

    callback_query.answer.assert_awaited_once()
    bot.send_message.assert_awaited_once()
    bot.edit_message_text.assert_not_called()


def test_show_screen_uses_edit_message_for_inline_keyboard_on_callback():
    callback_query = SimpleNamespace(answer=AsyncMock())
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        edit_message_text=AsyncMock(return_value=None),
        delete_message=AsyncMock(),
    )
    update = _build_update(callback_query=callback_query)
    context = _build_context(bot, last_message_id=100)
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("В меню", callback_data="main_menu")]]
    )

    asyncio.run(
        ScreenManager().show_screen(
            update,
            context,
            "Тест",
            reply_markup=reply_markup,
            prefer_new_on_message=False,
        )
    )

    callback_query.answer.assert_awaited_once()
    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_called()


def test_show_contacts_request_uses_reply_keyboard_with_contact_button(monkeypatch):
    answer_mock = AsyncMock()
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_answer", answer_mock)
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)

    update = SimpleNamespace(callback_query=SimpleNamespace())
    context = SimpleNamespace(user_data={})

    asyncio.run(bot_main.show_contacts_request(update, context))

    answer_mock.assert_awaited_once()
    show_mock.assert_awaited_once()
    reply_markup = show_mock.await_args.kwargs["reply_markup"]
    assert isinstance(reply_markup, ReplyKeyboardMarkup)
    assert bool(reply_markup.keyboard[0][0].request_contact) is True


def test_show_screen_falls_back_to_send_on_edit_timeout():
    callback_query = SimpleNamespace(answer=AsyncMock())
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=200)),
        edit_message_text=AsyncMock(side_effect=TimedOut("Timed out")),
        delete_message=AsyncMock(),
    )
    update = _build_update(callback_query=callback_query)
    context = _build_context(bot, last_message_id=100)
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("В меню", callback_data="main_menu")]]
    )

    asyncio.run(
        ScreenManager().show_screen(
            update,
            context,
            "Тест",
            reply_markup=reply_markup,
            prefer_new_on_message=False,
        )
    )

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_awaited_once()


def test_show_screen_send_timeout_does_not_raise():
    callback_query = SimpleNamespace(answer=AsyncMock())
    bot = SimpleNamespace(
        send_message=AsyncMock(side_effect=TimedOut("Timed out")),
        edit_message_text=AsyncMock(),
        delete_message=AsyncMock(),
    )
    update = _build_update(callback_query=callback_query)
    context = _build_context(bot, last_message_id=0)
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("В меню", callback_data="main_menu")]]
    )

    asyncio.run(
        ScreenManager().show_screen(
            update,
            context,
            "Тест",
            reply_markup=reply_markup,
            prefer_new_on_message=False,
        )
    )

    bot.send_message.assert_awaited_once()
