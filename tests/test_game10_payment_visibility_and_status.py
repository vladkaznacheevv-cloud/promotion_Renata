from __future__ import annotations

from types import SimpleNamespace

from telegram import InlineKeyboardMarkup

from telegram_bot import main as bot_main
from telegram_bot.keyboards import get_game10_kb
from core.api import webhooks as webhooks_api


def test_game10_test_button_visible_by_default_when_env_missing(monkeypatch):
    monkeypatch.delenv("GAME10_TEST_PAYMENT_ENABLED", raising=False)
    assert bot_main._env_flag_enabled_default_true("GAME10_TEST_PAYMENT_ENABLED") is True


def test_game10_test_button_hidden_when_env_false(monkeypatch):
    monkeypatch.setenv("GAME10_TEST_PAYMENT_ENABLED", "false")
    assert bot_main._env_flag_enabled_default_true("GAME10_TEST_PAYMENT_ENABLED") is False


def test_game10_keyboard_hides_or_shows_test_button():
    kb_hidden = get_game10_kb(show_test_payment=False)
    kb_shown = get_game10_kb(show_test_payment=True)
    assert isinstance(kb_hidden, InlineKeyboardMarkup)
    hidden_texts = [btn.text for row in kb_hidden.inline_keyboard for btn in row]
    shown_texts = [btn.text for row in kb_shown.inline_keyboard for btn in row]
    assert "Тестовая оплата 50 ₽" not in hidden_texts
    assert "Тестовая оплата 50 ₽" in shown_texts


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

    import asyncio

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

