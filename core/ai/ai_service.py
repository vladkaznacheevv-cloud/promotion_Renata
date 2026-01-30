import os
import logging
import asyncio
from typing import List, Tuple

from openai import OpenAI
from core.ai.prompts import SYSTEM_PROMPT
from core.events.service import EventService
from core.db import database as db

logger = logging.getLogger(__name__)


class AIService:

    def __init__(self, api_key: str = None, model: str = None):
        provider = os.getenv("AI_PROVIDER", "openrouter")

        api_key = api_key or os.getenv("AI_API_KEY")
        model = model or os.getenv("AI_MODEL", "mistralai/devstral-2512:free")

        if not api_key:
            self.client = None
            self.model = model
            self.system_prompt = SYSTEM_PROMPT
            return

        if provider == "openrouter":
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", ""),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "RenataPromotion"),
                },
            )
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = SYSTEM_PROMPT


    async def _events_facts(self, limit: int = 10) -> str:
        """Подгружаем актуальные мероприятия из PostgreSQL и делаем facts-блок."""
        if db.async_session is None:
            return ""
        try:
            async with db.async_session() as session:
                event_service = EventService(session)
                events = await event_service.list_active()
        except Exception as e:
            logger.exception("Failed to load events from DB: %s", e)
            return ""

        if not events:
            return "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ: сейчас нет активных мероприятий."

        lines = [
            "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ (используй только эти данные; если нужного нет — скажи, что уточнишь у менеджера):"
        ]
        for ev in events[:limit]:
            # добавь поля price/location/url если они есть в модели
            dt = ev.starts_at.strftime("%d.%m.%Y %H:%M") if ev.starts_at else "дата уточняется"
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
            events_facts = await self._events_facts()
            if events_facts:
                messages.append({"role": "system", "content": events_facts})
        if history:
            messages.extend(history[-10:])

        messages.append({"role": "user", "content": user_message})

        try:
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
