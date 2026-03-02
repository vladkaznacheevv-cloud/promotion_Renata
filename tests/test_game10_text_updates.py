from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram_bot import main as bot_main


def test_game10_intro_text_has_new_tail_after_health():
    text = bot_main.GAME10_SCREEN_TEXT
    assert "здоровье." in text
    assert "Это бережная методология собранная из системной психологии и нейропрактик." in text
    assert "Это бережная методология, собранная из системной психологии и нейропрактик." not in text
    assert "Я знаю что ты устала быть ответственной" in text
    tail = text.split("здоровье.", 1)[1]
    assert tail.lstrip().startswith("Это бережная методология собранная из системной психологии и нейропрактик.")


def test_game10_description_text_contains_updated_sections():
    text = bot_main.GAME10_DESCRIPTION_SCREEN_TEXT
    assert "Формат работы: 4 недели, 4 тематических блока." in text
    assert "Кто ведёт: Я, Рената Минакова." in text
    assert "ЧТО ЕЩЕ ВАС ЖДЁТ В СООБЩЕСТВЕ" in text
    assert "фокус-группа с дипломированным психологом" in text


def test_game10_screens_use_plain_text_parse_mode_none(monkeypatch):
    answer_mock = AsyncMock()
    show_mock = AsyncMock()
    monkeypatch.setattr(bot_main, "_answer", answer_mock)
    monkeypatch.setattr(bot_main, "_show_screen", show_mock)

    update = SimpleNamespace(callback_query=SimpleNamespace())
    context = SimpleNamespace(user_data={})

    asyncio.run(bot_main.show_private_channel(update, context))
    assert show_mock.await_args.kwargs["parse_mode"] is None

    show_mock.reset_mock()
    asyncio.run(bot_main.show_game10_description(update, context))
    assert show_mock.await_args.kwargs["parse_mode"] is None
