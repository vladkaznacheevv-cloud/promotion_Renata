from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram_bot import main as bot_main
from telegram_bot.contact_parser import ParsedContacts


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _setup_fake_services(monkeypatch, *, initial_email: str | None):
    user = SimpleNamespace(
        id=101,
        tg_id=777,
        first_name=None,
        phone=None,
        email=initial_email,
        username=None,
    )
    calls = {"book": 0}

    class FakeUserService:
        def __init__(self, _session):
            pass

        async def get_or_create_by_tg_id(self, **kwargs):
            if not user.first_name:
                user.first_name = kwargs.get("first_name")
            if not user.username:
                user.username = kwargs.get("username")
            return user

        async def partial_update_contacts(self, tg_id, *, name=None, phone=None, email=None, username=None):
            assert tg_id == user.tg_id
            if name and not user.first_name:
                user.first_name = name
            if phone and not user.phone:
                user.phone = phone
            if email and not user.email:
                user.email = email
            if username:
                user.username = username
            return user

    class FakeCRMService:
        def __init__(self, _session):
            pass

        async def touch_client_activity_by_tg_id(self, _tg_id):
            return user

    class FakeConsultationService:
        def __init__(self, _session):
            pass

        async def list_active(self, limit=50):
            _ = limit
            return [SimpleNamespace(id=11, type="individual"), SimpleNamespace(id=12, type="group")]

        async def book(self, **kwargs):
            calls["book"] += 1
            return SimpleNamespace(**kwargs)

    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(bot_main.db, "init_db", lambda: None)
    monkeypatch.setattr(bot_main.db, "async_session", lambda: _SessionCtx(session))
    monkeypatch.setattr(bot_main, "UserService", FakeUserService)
    monkeypatch.setattr(bot_main, "CRMService", FakeCRMService)
    monkeypatch.setattr(bot_main, "ConsultationService", FakeConsultationService)
    return user, calls


def test_save_consultation_lead_keeps_existing_email(monkeypatch):
    user, calls = _setup_fake_services(monkeypatch, initial_email="saved@example.com")
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=777, first_name="Test", last_name=None, username=None),
    )
    parsed = ParsedContacts(name="Иван", phone="+79991234567", email=None, username=None)

    result = asyncio.run(bot_main._save_consultation_lead(update, mode="individual", raw_text="Иван +7999", parsed=parsed))

    assert result["ok"] is True
    assert result["had_email_before"] is True
    assert result["has_email"] is True
    assert user.email == "saved@example.com"
    assert calls["book"] == 1


def test_save_consultation_lead_saves_email_when_missing(monkeypatch):
    user, calls = _setup_fake_services(monkeypatch, initial_email=None)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=777, first_name="Test", last_name=None, username=None),
    )
    parsed = ParsedContacts(name="Иван", phone=None, email="new@example.com", username=None)

    result = asyncio.run(
        bot_main._save_consultation_lead(
            update,
            mode="group",
            raw_text="Иван new@example.com",
            parsed=parsed,
        )
    )

    assert result["ok"] is True
    assert result["has_email"] is True
    assert user.email == "new@example.com"
    assert calls["book"] == 1


def test_handle_lead_message_shows_confirmation_not_menu(monkeypatch):
    monkeypatch.setattr(
        bot_main,
        "parse_contacts_from_message",
        lambda *_args, **_kwargs: ParsedContacts(name="Иван", phone="+79991234567", email=None, username=None),
    )
    monkeypatch.setattr(
        bot_main,
        "_save_consultation_lead",
        AsyncMock(
            return_value={
                "ok": True,
                "had_email_before": True,
                "has_email": True,
                "has_phone": True,
                "has_name": True,
                "has_username": False,
                "lead_saved": True,
            }
        ),
    )
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)
    monkeypatch.setattr(bot_main, "_send", AsyncMock())
    show_menu_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_main_menu_bottom", show_menu_mock)

    update = SimpleNamespace(
        message=SimpleNamespace(text="Иван +7 999 123 45 67"),
        effective_user=SimpleNamespace(id=777, first_name="Иван", last_name=None, username=None),
    )
    context = SimpleNamespace(user_data={bot_main.WAITING_LEAD_KEY: "individual"}, bot=SimpleNamespace())

    asyncio.run(bot_main.handle_lead_message(update, context))

    shown_text = str(show_mock.await_args.args[2])
    assert "Заявка принята" in shown_text
    assert "Email уже сохранён" in shown_text
    assert context.user_data.get(bot_main.WAITING_LEAD_KEY) is None
    show_menu_mock.assert_not_awaited()
