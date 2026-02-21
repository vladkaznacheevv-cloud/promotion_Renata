from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import List, Tuple

from openai import OpenAI
from sqlalchemy import select

from core.ai.prompts import SYSTEM_PROMPT
from core.catalog.models import CatalogItem
from core.consultations.models import Consultation, UserConsultation
from core.crm.models import GetCourseWebhookEvent
from core.db import database as db
from core.events.models import Event, UserEvent
from core.rag import RagRetriever, RagStore
from core.users.models import User

logger = logging.getLogger(__name__)


_DEFAULT_SYSTEM_PROMPT = (
    "Ты — Ассистент Ренаты Минаковой. "
    "Отвечай дружелюбно, коротко и по делу. "
    "Если не хватает данных, честно скажи об этом и задай уточняющий вопрос."
)

_MOJIBAKE_RE = re.compile(r"[РСЃ][\w\d]{0,3}")


class AIService:
    UNAVAILABLE_MESSAGE = "Ассистент временно недоступен"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        provider = (os.getenv("AI_PROVIDER", "openrouter") or "openrouter").strip().lower()
        api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY")
        if provider == "openrouter":
            self.model = (
                (model or "").strip()
                or (os.getenv("OPENROUTER_MODEL") or "").strip()
                or "minimax/minimax-m2.5"
            )
        else:
            self.model = (
                (model or "").strip()
                or (os.getenv("AI_MODEL") or "").strip()
                or "gpt-4o-mini"
            )
        self.system_prompt = self._safe_system_prompt(SYSTEM_PROMPT)
        self.reasoning_enabled = self._env_bool("OPENROUTER_REASONING", default=False)

        self.rag_enabled = self._env_bool("RAG_ENABLED", default=True)
        self.rag_top_k = self._env_int("RAG_TOP_K", default=5, min_value=1, max_value=20)
        self.rag_min_score = self._env_float("RAG_MIN_SCORE", default=0.08)
        rag_dir = (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"
        self.rag_retriever: RagRetriever | None = None
        if self.rag_enabled:
            self.rag_retriever = RagRetriever(store=RagStore(data_dir=rag_dir))

        self.client: OpenAI | None = None
        if not api_key:
            return

        if provider == "openrouter":
            referer = (
                os.getenv("OPENROUTER_HTTP_REFERER")
                or os.getenv("OPENROUTER_SITE_URL")
                or "https://example.com"
            )
            title = (
                os.getenv("OPENROUTER_X_TITLE")
                or os.getenv("OPENROUTER_APP_NAME")
                or "Renata Promotion"
            )
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": referer,
                    "X-Title": title,
                },
                timeout=15.0,
            )
        else:
            self.client = OpenAI(api_key=api_key, timeout=15.0)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = (os.getenv(name) or "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_int(name: str, default: int, min_value: int = 1, max_value: int = 10_000) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except Exception:
            return default
        return max(min_value, min(value, max_value))

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except Exception:
            return default

    @staticmethod
    def _safe_system_prompt(prompt: str) -> str:
        text = (prompt or "").strip()
        if not text:
            return _DEFAULT_SYSTEM_PROMPT
        mojibake_hits = len(_MOJIBAKE_RE.findall(text))
        if mojibake_hits > max(3, len(text) // 40):
            return _DEFAULT_SYSTEM_PROMPT
        return text

    @staticmethod
    def _fmt_dt(value: datetime | None) -> str:
        if value is None:
            return "дата уточняется"
        try:
            return value.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return "дата уточняется"

    @staticmethod
    def _fmt_price(value, currency: str = "RUB") -> str:
        try:
            if value is None:
                return "цена по запросу"
            amount = float(value)
            if amount <= 0:
                return "бесплатно"
            return f"{int(amount)} {currency}"
        except Exception:
            return "цена по запросу"

    @staticmethod
    def _short(value: str | None, limit: int = 220) -> str:
        text = (value or "").replace("\n", " ").strip()
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    async def _event_context(self, tg_id: int | None, limit: int = 10) -> tuple[str, dict[str, int]]:
        if db.async_session is None:
            return "", {"user_events": 0, "consultations": 0, "active_events": 0, "catalog": 0, "webhooks": 0}

        counts = {"user_events": 0, "consultations": 0, "active_events": 0, "catalog": 0, "webhooks": 0}
        try:
            async with db.async_session() as session:
                lines: list[str] = []

                user: User | None = None
                if tg_id is not None:
                    user_row = await session.execute(select(User).where(User.tg_id == tg_id).limit(1))
                    user = user_row.scalar_one_or_none()

                if user is not None:
                    user_events_rows = await session.execute(
                        select(Event.title, Event.starts_at, Event.location, Event.price, UserEvent.status)
                        .join(UserEvent, UserEvent.event_id == Event.id)
                        .where(UserEvent.user_id == user.id)
                        .order_by(UserEvent.updated_at.desc())
                        .limit(min(limit, 5))
                    )
                    user_events = list(user_events_rows.all())
                    counts["user_events"] = len(user_events)
                    if user_events:
                        lines.append("События пользователя:")
                        for row in user_events:
                            lines.append(
                                f"- {row[0]} | {self._fmt_dt(row[1])} | {row[2] or 'онлайн'} | {self._fmt_price(row[3])} | статус: {row[4] or 'unknown'}"
                            )

                    user_consult_rows = await session.execute(
                        select(
                            Consultation.title,
                            Consultation.type,
                            Consultation.price,
                            UserConsultation.status,
                            UserConsultation.scheduled_at,
                        )
                        .join(UserConsultation, UserConsultation.consultation_id == Consultation.id)
                        .where(UserConsultation.user_id == user.id)
                        .order_by(UserConsultation.updated_at.desc())
                        .limit(min(limit, 5))
                    )
                    user_consults = list(user_consult_rows.all())
                    counts["consultations"] = len(user_consults)
                    if user_consults:
                        lines.append("Консультации пользователя:")
                        for row in user_consults:
                            lines.append(
                                f"- {row[0]} ({row[1] or 'формат не указан'}) | {self._fmt_price(row[2])} | {self._fmt_dt(row[4])} | статус: {row[3] or 'unknown'}"
                            )

                active_events_rows = await session.execute(
                    select(Event.title, Event.starts_at, Event.location, Event.price, Event.link_getcourse)
                    .where(Event.is_active.is_(True))
                    .order_by(Event.starts_at.asc(), Event.id.desc())
                    .limit(min(limit, 5))
                )
                active_events = list(active_events_rows.all())
                counts["active_events"] = len(active_events)
                if active_events:
                    lines.append("Актуальные мероприятия:")
                    for row in active_events:
                        lines.append(
                            f"- {row[0]} | {self._fmt_dt(row[1])} | {row[2] or 'онлайн'} | {self._fmt_price(row[3])} | ссылка: {row[4] or 'уточняется'}"
                        )

                catalog_rows = await session.execute(
                    select(CatalogItem.title, CatalogItem.price, CatalogItem.currency, CatalogItem.link_getcourse)
                    .where(CatalogItem.status == "active")
                    .order_by(CatalogItem.updated_at.desc(), CatalogItem.id.desc())
                    .limit(min(limit, 5))
                )
                catalog_items = list(catalog_rows.all())
                counts["catalog"] = len(catalog_items)
                if catalog_items:
                    lines.append("Каталог:")
                    for row in catalog_items:
                        lines.append(
                            f"- {row[0]} | {self._fmt_price(row[1], row[2] or 'RUB')} | ссылка: {row[3] or 'уточняется'}"
                        )

                webhook_rows = await session.execute(
                    select(
                        GetCourseWebhookEvent.event_type,
                        GetCourseWebhookEvent.status,
                        GetCourseWebhookEvent.amount,
                        GetCourseWebhookEvent.currency,
                        GetCourseWebhookEvent.received_at,
                    )
                    .order_by(GetCourseWebhookEvent.received_at.desc())
                    .limit(min(limit, 5))
                )
                webhook_events = list(webhook_rows.all())
                counts["webhooks"] = len(webhook_events)
                if webhook_events:
                    lines.append("Последние webhook-события GetCourse:")
                    for row in webhook_events:
                        lines.append(
                            f"- {row[0] or 'unknown'} | статус: {row[1] or 'unknown'} | сумма: {self._fmt_price(row[2], row[3] or 'RUB')} | {self._fmt_dt(row[4])}"
                        )

                return "\n".join(lines).strip(), counts
        except Exception as e:
            logger.warning("Failed to build event context: %s", e.__class__.__name__)
            return "", counts

    def _rag_context(self, query: str) -> tuple[str, str, int]:
        if not self.rag_enabled or self.rag_retriever is None:
            return "", "low", 0

        try:
            result = self.rag_retriever.retrieve(
                query=query,
                k=self.rag_top_k,
                min_score=self.rag_min_score,
            )
        except Exception as e:
            logger.warning("RAG retrieve failed: %s", e.__class__.__name__)
            return "", "low", 0

        if not result.top_chunks:
            return "", result.confidence, 0

        lines = ["Контекст базы знаний:"]
        for idx, chunk in enumerate(result.top_chunks, start=1):
            lines.append(
                f"{idx}. {chunk.title} ({chunk.source}): {self._short(chunk.text, limit=520)}"
            )
        return "\n".join(lines), result.confidence, len(result.top_chunks)

    def _build_request_kwargs(
        self,
        *,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "timeout": 15.0,
        }
        if self.reasoning_enabled:
            kwargs["extra_body"] = {"reasoning": {"enabled": True}}
        return kwargs

    async def get_response(
        self,
        user_message: str,
        history: List[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        include_events: bool = True,
        tg_id: int | None = None,
    ) -> str:
        if not self.client:
            return self.UNAVAILABLE_MESSAGE

        developer_prompt = (
            "Приоритет источников ответа: "
            "1) контекст CRM и событий, "
            "2) контекст локальной базы знаний, "
            "3) общие знания модели. "
            "Не выдумывай факты о проекте, если их нет в контексте. "
            "Не упоминай внутренние файлы, таблицы, переменные и служебные поля. "
            "Стиль: Ассистент Ренаты, коротко, дружелюбно, с уточняющим вопросом при нехватке данных."
        )

        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": developer_prompt},
        ]

        rag_confidence = "low"
        rag_chunks_count = 0
        event_context = ""
        rag_context = ""

        if include_events:
            event_context, event_counts = await self._event_context(tg_id=tg_id, limit=10)
            if event_context:
                messages.append({"role": "system", "content": f"Контекст CRM и событий:\n{event_context}"})
            rag_context, rag_confidence, rag_chunks_count = self._rag_context(user_message)
            if rag_context:
                messages.append({"role": "system", "content": rag_context})

            if not rag_context or rag_confidence == "low":
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Если контекста недостаточно, используй только общие знания без конкретных утверждений "
                            "о внутренних процессах, ценах, расписании и ссылках проекта."
                        ),
                    }
                )

            logger.debug(
                "assistant_context: event_chars=%s rag_chunks=%s rag_confidence=%s counters=%s",
                len(event_context),
                rag_chunks_count,
                rag_confidence,
                event_counts,
            )

        if history:
            messages.extend(history[-10:])

        messages.append({"role": "user", "content": user_message})
        request_kwargs = self._build_request_kwargs(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **request_kwargs,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return "Не получилось сформировать ответ. Попробуйте, пожалуйста, еще раз."
            return content
        except Exception as e:
            logger.warning("AI request failed: %s", e.__class__.__name__)
            return "Извините, сейчас не получилось ответить. Попробуйте чуть позже."

    async def chat(
        self,
        user_message: str,
        chat_history: List[dict] | None = None,
        tg_id: int | None = None,
    ) -> Tuple[str, List[dict]]:
        response = await self.get_response(
            user_message=user_message,
            history=chat_history,
            include_events=True,
            tg_id=tg_id,
        )
        new_history = chat_history or []
        new_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response},
            ]
        )
        return response, new_history

    async def ping(self) -> tuple[bool, str]:
        if not self.client:
            return False, self.UNAVAILABLE_MESSAGE

        request_kwargs = self._build_request_kwargs(
            messages=[
                {"role": "system", "content": "Отвечай кратко."},
                {"role": "user", "content": "Ответь одним коротким предложением на русском."},
            ],
            max_tokens=80,
            temperature=0.0,
        )
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **request_kwargs,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return False, "empty_reply"
            return True, content
        except Exception as e:
            logger.warning("AI ping failed: %s", e.__class__.__name__)
            return False, f"provider_error:{e.__class__.__name__}"
