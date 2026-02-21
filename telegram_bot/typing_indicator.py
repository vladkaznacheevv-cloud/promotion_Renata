from __future__ import annotations

import asyncio
import contextlib
import logging

from telegram import Bot
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)

TYPING_INTERVAL_SECONDS = 4.0


class TypingIndicator:
    def __init__(self, bot: Bot, chat_id: int, *, interval_seconds: float = TYPING_INTERVAL_SECONDS):
        self._bot = bot
        self._chat_id = chat_id
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        await self._send_typing()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        task = self._task
        self._task = None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_seconds)
            await self._send_typing()

    async def _send_typing(self) -> None:
        try:
            await self._bot.send_chat_action(chat_id=self._chat_id, action=ChatAction.TYPING)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Typing indicator failed for chat_id=%s: %s", self._chat_id, exc)
