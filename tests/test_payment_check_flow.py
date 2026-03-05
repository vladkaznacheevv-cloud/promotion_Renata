from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardMarkup

from telegram_bot import main as bot_main


def _callbacks(markup: InlineKeyboardMarkup) -> list[str]:
    return [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", None)
    ]


def test_send_game10_payment_qr_and_screen_contains_pay_check_button(monkeypatch):
    monkeypatch.setattr(bot_main, "_build_qr_png", lambda value: None)
    monkeypatch.setattr(bot_main, "_delete_last_game10_payment_ui_message", AsyncMock())

    send_mock = AsyncMock(return_value=SimpleNamespace(message_id=101))
    context = SimpleNamespace(bot=SimpleNamespace(send_message=send_mock), user_data={})
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=777))

    asyncio.run(
        bot_main._send_game10_payment_qr_and_screen(
            update,
            context,
            confirmation_url="https://example.com/pay",
            payment_id="yk_123",
            amount_rub=5000,
        )
    )

    kwargs = send_mock.await_args.kwargs
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert "pay_check:yk_123" in _callbacks(markup)


def test_game10_pay_check_calls_backend_and_handles_forbidden(monkeypatch):
    monkeypatch.setattr(bot_main, "_answer", AsyncMock())
    monkeypatch.setattr(
        bot_main,
        "_check_game10_payment_status_backend",
        AsyncMock(return_value={"ok": True, "status": "succeeded", "result": "invite_failed", "error_type": "Forbidden"}),
    )
    monkeypatch.setattr(bot_main, "_get_last_game10_payment_ui_kb", lambda context, payment_id: None)
    monkeypatch.setattr(bot_main, "_game10_kb_for_update", lambda update: InlineKeyboardMarkup([]))
    show_screen_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_screen_mock)

    update = SimpleNamespace(
        callback_query=SimpleNamespace(data="pay_check:yk_forbidden_1"),
        effective_user=SimpleNamespace(id=321),
    )
    context = SimpleNamespace(user_data={})

    asyncio.run(bot_main.game10_pay_check(update, context))

    bot_main._check_game10_payment_status_backend.assert_awaited_once_with("yk_forbidden_1", tg_id=321)
    assert context.user_data["last_payment_id"] == "yk_forbidden_1"
    shown_texts = [str(call.args[2]) for call in show_screen_mock.await_args_list]
    assert any("/start" in text for text in shown_texts)


def test_start_with_pay_deeplink_shows_check_button(monkeypatch):
    show_screen_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_screen_mock)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=321),
        effective_chat=SimpleNamespace(id=777),
    )
    context = SimpleNamespace(args=["pay_yk_777"], user_data={})

    asyncio.run(bot_main.start(update, context))

    assert context.user_data["last_payment_id"] == "yk_777"
    text = str(show_screen_mock.await_args.args[2])
    assert "Спасибо за оплату" in text
    markup = show_screen_mock.await_args.kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert "pay_check:yk_777" in _callbacks(markup)


def test_game10_pay_check_pending_status_is_localized(monkeypatch):
    monkeypatch.setattr(bot_main, "_answer", AsyncMock())
    monkeypatch.setattr(
        bot_main,
        "_check_game10_payment_status_backend",
        AsyncMock(return_value={"ok": True, "status": "pending", "result": "pending"}),
    )
    monkeypatch.setattr(bot_main, "_get_last_game10_payment_ui_kb", lambda context, payment_id: None)
    monkeypatch.setattr(bot_main, "_game10_kb_for_update", lambda update: InlineKeyboardMarkup([]))
    show_screen_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_screen_mock)

    update = SimpleNamespace(
        callback_query=SimpleNamespace(data="pay_check:yk_pending_1"),
        effective_user=SimpleNamespace(id=321),
    )
    context = SimpleNamespace(user_data={})

    asyncio.run(bot_main.game10_pay_check(update, context))

    pending_call = next(
        call
        for call in show_screen_mock.await_args_list
        if "Платёж ещё обрабатывается" in str(call.args[2])
    )
    assert pending_call.kwargs.get("parse_mode") is None
