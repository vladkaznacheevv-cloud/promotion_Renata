from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

from telegram_bot import main as bot_main


def test_main_menu_degrades_if_reset_raises(monkeypatch):
    monkeypatch.setattr(bot_main, "_answer", AsyncMock())
    monkeypatch.setattr(bot_main, "_reset_states", lambda context: (_ for _ in ()).throw(RuntimeError("db down")))
    show_menu_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_show_main_menu_bottom", show_menu_mock)

    update = SimpleNamespace(callback_query=SimpleNamespace(), effective_chat=SimpleNamespace(id=100))
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_message=AsyncMock()))

    asyncio.run(bot_main.main_menu(update, context))

    show_menu_mock.assert_awaited_once_with(update, context)


def test_guard_user_handler_blocks_parallel_calls(monkeypatch):
    bot_main.USER_BUSY_IDS.clear()
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = {"count": 0}

    async def _slow_handler(update, context):
        calls["count"] += 1
        entered.set()
        await release.wait()

    guarded = bot_main._guard_user_handler(_slow_handler, action="slow_handler", busy_mode="notify")
    reply_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_reply", reply_mock)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        effective_message=SimpleNamespace(),
        callback_query=None,
        message=SimpleNamespace(),
    )
    context = SimpleNamespace(user_data={})

    async def _run() -> None:
        first_task = asyncio.create_task(guarded(update, context))
        await entered.wait()
        with pytest.raises(ApplicationHandlerStop):
            await guarded(update, context)
        release.set()
        await first_task

    asyncio.run(_run())

    assert calls["count"] == 1
    assert reply_mock.await_count == 1
    bot_main.USER_BUSY_IDS.clear()
