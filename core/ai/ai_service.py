import logging
import asyncio
from typing import List, Tuple

from openai import OpenAI
from core.ai.prompts import SYSTEM_PROMPT

from core.db.database import async_session
from core.events.service import EventService

logger = logging.getLogger(__name__)


class AIService:
    """Сервис AI-ассистента Mimo"""

    def __init__(self, api_key: str = None, model: str = "mimo-v2-flash"):
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model
        self.system_prompt = SYSTEM_PROMPT

    async def _events_facts(self, limit: int = 10) -> str:
        """Подгружаем актуальные мероприятия из PostgreSQL и делаем facts-блок."""
        try:
            async with async_session() as session:
                event_service = EventService(session)
                events = await event_service.get_active()
        except Exception as e:
            logger.exception("Failed to load events from DB: %s", e)
            return "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ: (ошибка загрузки из базы)"

        if not events:
            return "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ: сейчас нет активных мероприятий."

        lines = [
            "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ (используй только эти данные; если нужного нет — скажи, что уточнишь у менеджера):"
        ]
        for ev in events[:limit]:
            # добавь поля price/location/url если они есть в модели
            dt = ev.date.strftime("%d.%m.%Y %H:%M")
            lines.append(f"- id={ev.id} | {ev.title} | {dt}")
        return "\n".join(lines)

    async def get_response(
        self,
        user_message: str,
        history: List[dict] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        include_events: bool = True,
    ) -> str:
        """Получить ответ от AI"""
        if not self.client:
            return "AI не настроен. Обратитесь к администратору."

        messages = [{"role": "system", "content": self.system_prompt}]

        if include_events:
            messages.append({"role": "system", "content": await self._events_facts()})

        if history:
            messages.extend(history[-10:])

        messages.append({"role": "user", "content": user_message})

        try:
            # sync OpenAI call -> в отдельный поток, чтобы не блокировать бота
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI error: {e}")
            return "Извините, произошла ошибка. Попробуйте позже."

    async def chat(self, user_message: str, chat_history: List[dict] = None) -> Tuple[str, List[dict]]:
        """Полный цикл чата с историей"""
        response = await self.get_response(user_message, chat_history, include_events=True)

        new_history = chat_history or []
        new_history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response},
        ])
        return response, new_history
