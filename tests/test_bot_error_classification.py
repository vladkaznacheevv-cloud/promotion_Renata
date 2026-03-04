from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy.exc import SQLAlchemyError
from telegram.error import TimedOut

from telegram_bot import main as bot_main


def test_is_db_exception_false_for_telegram_timeout():
    assert bot_main._is_db_exception(TimedOut("Timed out")) is False


def test_is_db_exception_true_for_sqlalchemy():
    assert bot_main._is_db_exception(SQLAlchemyError("db")) is True


def test_is_db_exception_true_for_asyncpg_module_like_error():
    AsyncpgLikeError = type("PostgresError", (Exception,), {"__module__": "asyncpg.exceptions"})
    assert bot_main._is_db_exception(AsyncpgLikeError("db")) is True


def test_on_error_timeout_does_not_call_db_unavailable(monkeypatch):
    notify_db_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_notify_db_unavailable", notify_db_mock)

    update = SimpleNamespace(callback_query=SimpleNamespace())
    context = SimpleNamespace(error=TimedOut("Timed out"))

    asyncio.run(bot_main.on_error(update, context))

    notify_db_mock.assert_not_called()


def test_notify_db_unavailable_edit_timeout_logged_as_net(monkeypatch):
    answer_mock = AsyncMock()
    edit_mock = AsyncMock(side_effect=TimedOut("Timed out"))
    log_db_mock = Mock()
    log_net_mock = Mock()
    monkeypatch.setattr(bot_main, "_answer", answer_mock)
    monkeypatch.setattr(bot_main, "_edit", edit_mock)
    monkeypatch.setattr(bot_main, "_log_db_issue", log_db_mock)
    monkeypatch.setattr(bot_main, "_log_net_issue", log_net_mock)

    update = SimpleNamespace(callback_query=SimpleNamespace(), effective_message=None)

    asyncio.run(bot_main._notify_db_unavailable(update, RuntimeError("db"), scope="test_scope"))

    assert any(call.args[0] == "test_scope" for call in log_db_mock.call_args_list)
    assert not any(call.args[0] == "notify_db_unavailable_edit" for call in log_db_mock.call_args_list)
    assert any(call.args[0] == "notify_db_unavailable_edit" for call in log_net_mock.call_args_list)
