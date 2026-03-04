from __future__ import annotations

import asyncio
from types import SimpleNamespace

from telegram import InlineKeyboardMarkup

from core.api import webhooks as webhooks_api
from telegram_bot import main as bot_main
from telegram_bot.keyboards import get_game10_kb, get_main_menu


def test_game10_keyboard_has_only_main_payment_button():
    kb = get_game10_kb(show_test_payment=True)
    assert isinstance(kb, InlineKeyboardMarkup)
    callback_data = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert "private_channel_payment_info" in callback_data
    assert "game10_pay_test" not in callback_data


def test_main_menu_order_game10_then_courses():
    kb = get_main_menu()
    texts = [row[0].text for row in kb.inline_keyboard]
    assert texts[0] == "«Игра 10:0»"
    assert texts[1] == "Авторский курс лекций"
    assert kb.inline_keyboard[0][0].callback_data == "private_channel"
    assert kb.inline_keyboard[1][0].callback_data == "courses"


def test_payment_ui_strings_do_not_contain_question_garbage():
    strings = [
        bot_main.PAYMENT_CREATING_SCREEN,
        bot_main.PAYMENT_NEED_CONTACT_SCREEN,
        bot_main.PAYMENT_ASK_PHONE_SCREEN,
        bot_main.PAYMENT_ASK_EMAIL_SCREEN,
        bot_main.PAYMENT_CONTACT_SAVED_SCREEN,
        bot_main.PAYMENT_CANCELLED_SCREEN,
        bot_main.PAYMENT_LINK_READY_SCREEN,
        bot_main.PAYMENT_EXPIRED_HINT,
    ]
    for value in strings:
        assert "????" not in value
        assert value.strip() and any(ch != "?" for ch in value)


def test_process_game10_payment_success_returns_already_member(monkeypatch):
    calls = {"already_msg": 0, "invite": 0, "paid_msg": 0, "mark_paid": 0}

    class _DummyCRMService:
        def __init__(self, db):
            self.db = db

        async def mark_private_channel_paid(self, tg_id, ensure_invite=False):
            calls["mark_paid"] += 1
            return True

    async def _fake_get_chat_member_status(*, chat_id, user_id):
        return "member"

    async def _fake_send_already_member_message(*, tg_id):
        calls["already_msg"] += 1

    async def _fake_create_invite(*, tg_id, payment_id):
        calls["invite"] += 1
        return "https://example.com/invite"

    async def _fake_send_paid_message(*, tg_id, invite_link):
        calls["paid_msg"] += 1

    monkeypatch.setenv("TELEGRAM_PRIVATE_CHANNEL_ID", "-1003326379979")
    monkeypatch.setattr(webhooks_api, "CRMService", _DummyCRMService)
    monkeypatch.setattr(webhooks_api, "_get_chat_member_status", _fake_get_chat_member_status)
    monkeypatch.setattr(webhooks_api, "_send_game10_already_member_message", _fake_send_already_member_message)
    monkeypatch.setattr(webhooks_api, "_create_game10_join_request_link", _fake_create_invite)
    monkeypatch.setattr(webhooks_api, "_send_game10_paid_message", _fake_send_paid_message)

    async def _fake_upsert_crm_game10_payment(*, db, tg_id, payment_id):
        return "created"

    monkeypatch.setattr(webhooks_api, "_upsert_crm_game10_payment", _fake_upsert_crm_game10_payment)

    result = asyncio.run(
        webhooks_api.process_game10_payment_success(
            db=SimpleNamespace(),
            payment_id="yk_member_1",
            tg_id=123456,
        )
    )
    assert result["result"] == "already_member"
    assert result["already_in_channel"] is True
    assert calls["mark_paid"] == 1
    assert calls["already_msg"] == 1
    assert calls["invite"] == 0
    assert calls["paid_msg"] == 0


def test_process_game10_payment_success_sets_invite_sent_only_after_successful_delivery(monkeypatch):
    class _DummyCRMService:
        def __init__(self, db):
            self.db = db

        async def mark_private_channel_paid(self, tg_id, ensure_invite=False):
            return True

    async def _fake_get_chat_member_status(*, chat_id, user_id):
        return None

    async def _fake_create_invite(*, tg_id, payment_id):
        return "https://example.com/invite"

    async def _fake_send_paid_message(*, tg_id, invite_link):
        return {"ok": True, "error_type": None}

    async def _fake_upsert_crm_game10_payment(*, db, tg_id, payment_id):
        return "created"

    monkeypatch.setenv("TELEGRAM_PRIVATE_CHANNEL_ID", "-1003326379979")
    monkeypatch.setattr(webhooks_api, "CRMService", _DummyCRMService)
    monkeypatch.setattr(webhooks_api, "_get_chat_member_status", _fake_get_chat_member_status)
    monkeypatch.setattr(webhooks_api, "_create_game10_join_request_link", _fake_create_invite)
    monkeypatch.setattr(webhooks_api, "_send_game10_paid_message", _fake_send_paid_message)
    monkeypatch.setattr(webhooks_api, "_upsert_crm_game10_payment", _fake_upsert_crm_game10_payment)

    result = asyncio.run(
        webhooks_api.process_game10_payment_success(
            db=SimpleNamespace(),
            payment_id="yk_ok_1",
            tg_id=123456,
        )
    )

    assert result["result"] == "invite_sent"
    assert result["invite_sent"] is True
    assert result["already_in_channel"] is False


def test_process_game10_payment_success_returns_invite_failed_on_telegram_error(monkeypatch):
    class _DummyCRMService:
        def __init__(self, db):
            self.db = db

        async def mark_private_channel_paid(self, tg_id, ensure_invite=False):
            return True

    async def _fake_get_chat_member_status(*, chat_id, user_id):
        return None

    async def _fake_create_invite(*, tg_id, payment_id):
        return "https://example.com/invite"

    async def _fake_send_paid_message(*, tg_id, invite_link):
        return {"ok": False, "error_type": "Forbidden"}

    async def _fake_upsert_crm_game10_payment(*, db, tg_id, payment_id):
        return "created"

    monkeypatch.setenv("TELEGRAM_PRIVATE_CHANNEL_ID", "-1003326379979")
    monkeypatch.setattr(webhooks_api, "CRMService", _DummyCRMService)
    monkeypatch.setattr(webhooks_api, "_get_chat_member_status", _fake_get_chat_member_status)
    monkeypatch.setattr(webhooks_api, "_create_game10_join_request_link", _fake_create_invite)
    monkeypatch.setattr(webhooks_api, "_send_game10_paid_message", _fake_send_paid_message)
    monkeypatch.setattr(webhooks_api, "_upsert_crm_game10_payment", _fake_upsert_crm_game10_payment)

    result = asyncio.run(
        webhooks_api.process_game10_payment_success(
            db=SimpleNamespace(),
            payment_id="yk_err_1",
            tg_id=123456,
        )
    )

    assert result["result"] == "invite_failed"
    assert result["invite_sent"] is False
    assert result["error_type"] == "Forbidden"
