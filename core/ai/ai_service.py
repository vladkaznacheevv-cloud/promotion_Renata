from __future__ import annotations

import asyncio
import logging
import os
from typing import List, Tuple

from openai import OpenAI
from sqlalchemy import select

from core.ai.prompts import SYSTEM_PROMPT
from core.db import database as db
from core.events.service import EventService
from core.catalog.models import CatalogItem

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
        """Load active events from DB and pass only factual data to AI."""
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
            "АКТУАЛЬНЫЕ МЕРОПРИЯТИЯ (используй только эти поля: title/date/location/price/description/link_getcourse):"
        ]
        for ev in events[:limit]:
            dt = ev.starts_at.strftime("%d.%m.%Y %H:%M") if ev.starts_at else "дата уточняется"
            price = int(ev.price) if ev.price is not None else 0
            location = ev.location or "не указано"
            description = ev.description or "описание не указано"
            link = ev.link_getcourse or "ссылка не указана"
            lines.append(
                f"- id={ev.id} | title={ev.title} | date={dt} | location={location} | price={price} RUB | description={description} | link_getcourse={link}"
            )
        return "\n".join(lines)

    async def _catalog_facts(self, limit: int = 5) -> str:
        """Load active catalog items and pass only factual data to AI."""
        if db.async_session is None:
            return ""
        try:
            async with db.async_session() as session:
                rows = await session.execute(
                    select(CatalogItem)
                    .where(CatalogItem.status == "active")
                    .order_by(CatalogItem.updated_at.desc().nulls_last(), CatalogItem.id.desc())
                    .limit(limit)
                )
                items = rows.scalars().all()
        except Exception as e:
            logger.exception("Failed to load catalog from DB: %s", e)
            return ""

        if not items:
            return "КАТАЛОГ ОНЛАЙН-КУРСОВ: активных позиций нет."

        lines = [
            "КАТАЛОГ ОНЛАЙН-КУРСОВ (используй только эти поля: title/description/price/link_getcourse):"
        ]
        for item in items:
            price = int(item.price) if item.price is not None else 0
            description = item.description or "описание не указано"
            link = item.link_getcourse or "ссылка не указана"
            lines.append(
                f"- id={item.id} | title={item.title} | price={price} RUB | description={description} | link_getcourse={link}"
            )
        return "\n".join(lines)

    async def get_response(
        self,
        user_message: str,
        history: List[dict] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        include_events: bool = True,
    ) -> str:
        """Get AI response."""
        if not self.client:
            return "AI не настроен. Обратитесь к администратору."

        messages = [{"role": "system", "content": self.system_prompt}]

        if include_events:
            events_facts = await self._events_facts()
            if events_facts:
                messages.append({"role": "system", "content": events_facts})
            catalog_facts = await self._catalog_facts()
            if catalog_facts:
                messages.append({"role": "system", "content": catalog_facts})
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Запрещено добавлять факты сверх переданных полей. "
                        "Если данных не хватает, прямо скажи об этом и предложи уточнить у менеджера. "
                        "Если вопрос про курс/обучение/онлайн, предложи команду /courses и перечисли 1-3 релевантные позиции из каталога."
                    ),
                }
            )

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
            logger.error("AI error: %s", e)
            return "Извините, произошла ошибка. Попробуйте позже."

    async def chat(self, user_message: str, chat_history: List[dict] = None) -> Tuple[str, List[dict]]:
        """Chat cycle with history."""
        response = await self.get_response(user_message, chat_history, include_events=True)

        new_history = chat_history or []
        new_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response},
            ]
        )
        return response, new_history
