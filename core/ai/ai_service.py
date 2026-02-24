from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date as dt_date, datetime, time as dt_time
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
_RAG_FOCUS_PREFIX_RE = re.compile(r"^\s*\[FOCUS:(?P<name>[A-Z0-9_/-]+)\]\s*", re.IGNORECASE)


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
        self.rag_top_k = self._env_int("RAG_TOP_K", default=6, min_value=1, max_value=20)
        self.rag_min_score = self._env_float("RAG_MIN_SCORE", default=0.08)
        self.rag_max_context_chars = self._env_int("RAG_MAX_CONTEXT_CHARS", default=3800, min_value=800, max_value=12000)
        rag_dir = (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"
        self.rag_data_dir = rag_dir
        self.rag_retriever: RagRetriever | None = None
        self._last_trace: dict[str, object] = {}
        if self.rag_enabled:
            self.rag_retriever = RagRetriever(store=RagStore(data_dir=rag_dir))
            self._log_rag_startup_summary()

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

    def _log_rag_startup_summary(self) -> None:
        if not self.rag_enabled or self.rag_retriever is None:
            logger.info("RAG startup: enabled=%s collections=0 docs=0", False)
            return
        try:
            store = self.rag_retriever.store
            collections = store.list_collections(self.rag_data_dir)
            docs_total = 0
            for collection_dir in collections.values():
                docs_total += len(list(store._iter_files(collection_dir=collection_dir)))
            logger.info(
                "RAG startup: enabled=%s collections=%s docs=%s",
                True,
                len(collections),
                docs_total,
            )
        except Exception as e:
            logger.warning("RAG startup summary failed: %s", e.__class__.__name__)

    @staticmethod
    def _detect_need_themes(text: str | None) -> list[str]:
        normalized = (text or "").lower().replace("ё", "е")
        groups: list[tuple[str, tuple[str, ...]]] = [
            ("relationships", ("отношен", "партнер", "муж", "жена", "развод", "конфликт", "семья")),
            ("anxiety", ("тревог", "страх", "паник", "напряжен", "беспокой", "тревожно")),
            ("self_esteem", ("самооцен", "уверенн", "неуверенн", "стыд", "вина", "ценност")),
            ("career", ("карьер", "работ", "бизнес", "деньг", "доход", "професс", "реализац")),
            ("burnout", ("выгоран", "устал", "нет сил", "апат", "истощ", "перегруз")),
            ("crisis", ("кризис", "тупик", "не понимаю", "развал", "потеря", "сломал")),
            ("psychologist_growth", ("психолог", "клиент", "супервиз", "практик", "терапевт", "кейс")),
        ]
        detected: list[str] = []
        for name, keywords in groups:
            if any(keyword in normalized for keyword in keywords):
                detected.append(name)
        return detected[:3]

    @staticmethod
    def _themes_hint_text(themes: list[str]) -> str:
        if not themes:
            return ""
        labels = {
            "relationships": "отношения",
            "anxiety": "тревога/напряжение",
            "self_esteem": "самооценка/уверенность",
            "career": "карьера/бизнес/деньги",
            "burnout": "выгорание/истощение",
            "crisis": "кризис/тупик",
            "psychologist_growth": "профрост психолога/супервизия",
        }
        return ", ".join(labels.get(item, item) for item in themes)

    def _sales_guidance_prompt(self, *, user_message: str, response_mode: str) -> str:
        sales_mode = response_mode == "sales" or "[SALES_MODE]" in (user_message or "")
        clean_message = (user_message or "").replace("[SALES_MODE]", " ").strip()
        themes = self._detect_need_themes(clean_message)
        themes_text = self._themes_hint_text(themes)
        base = (
            "Задача: помочь с выбором по потребности, не навязывать один продукт. "
            "Если есть релевантные данные в CRM/RAG, предложи 1-3 варианта и кратко объясни, почему они подходят. "
            "Обязательно укажи следующий шаг: перейти в раздел, записаться, задать уточняющий вопрос или оставить контакты менеджеру. "
            "Если точных данных о ведущих/цене/расписании нет в контексте, прямо скажи, что не видишь данных, и не выдумывай."
        )
        if themes_text:
            base += f" Определи это как вероятную потребность пользователя: {themes_text}."
        if sales_mode:
            base += (
                " SALES MODE: ask at most one clarifying question about the need, "
                "then suggest one primary option (focused product if present) and one alternative only if relevant. "
                "Use CRM/RAG facts for format, price, schedule/start, and what is included. "
                "End with a clear CTA: sign up / leave contacts / open a relevant section."
            )
        elif response_mode == "auto_lite":
            base += (
                " Формат ответа для свободного текста: 3-7 коротких предложений, "
                "без длинных вводных. Можно использовать список из 1-3 пунктов."
            )
        return base

    def _trim_rag_context(self, rag_context: str) -> str:
        text = (rag_context or "").strip()
        if not text:
            return ""
        if len(text) <= self.rag_max_context_chars:
            return text
        return text[: self.rag_max_context_chars].rstrip() + "..."

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
            return "date TBD"
        try:
            return value.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return "date TBD"

    @staticmethod
    def _fmt_price(value, currency: str = "RUB") -> str:
        try:
            if value is None:
                return "price on request"
            amount = float(value)
            if amount <= 0:
                return "free"
            return f"{int(amount)} {currency}"
        except Exception:
            return "price on request"

    @staticmethod
    def _short(value: str | None, limit: int = 220) -> str:
        text = (value or "").replace("\n", " ").strip()
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."


    @staticmethod
    def _fmt_date(value) -> str:
        if value is None:
            return ""
        try:
            if isinstance(value, datetime):
                return value.strftime("%d.%m.%Y")
            if isinstance(value, dt_date):
                return value.strftime("%d.%m.%Y")
            text = str(value).strip()
            if not text:
                return ""
            if len(text) >= 10 and text[4] == "-" and text[7] == "-":
                yyyy, mm, dd = text[:10].split("-")
                return f"{dd}.{mm}.{yyyy}"
            return text
        except Exception:
            return str(value)

    @staticmethod
    def _fmt_time(value) -> str:
        if value is None:
            return ""
        try:
            if isinstance(value, dt_time):
                return value.strftime("%H:%M")
            text = str(value).strip()
            if not text:
                return ""
            return text[:5] if ":" in text else text
        except Exception:
            return str(value)

    @classmethod
    def _time_range_text(cls, start_value, end_value) -> str:
        start = cls._fmt_time(start_value)
        end = cls._fmt_time(end_value)
        if start and end:
            return f"{start}-{end}"
        return start or end

    @staticmethod
    def _parse_json_field(value):
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_query_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9\u0430-\u044f]+", " ", value.lower().replace("\u0451", "\u0435")).strip()

    def _event_match_score(self, event: Event, query: str | None) -> int:
        normalized_query = self._normalize_query_text(query)
        if not normalized_query:
            return 0
        title = self._normalize_query_text(getattr(event, "title", None))
        description = self._normalize_query_text(getattr(event, "description", None))
        haystack = " ".join(part for part in (title, description) if part).strip()
        if not haystack:
            return 0
        score = 0
        if title and title in normalized_query:
            score += 8
        if normalized_query in haystack:
            score += 6
        for token in [t for t in normalized_query.split() if len(t) >= 3]:
            if token in title:
                score += 2
            elif token in haystack:
                score += 1
        return score

    def _event_schedule_summary(self, event: Event) -> str:
        schedule_type = (getattr(event, "schedule_type", None) or "").strip() or "one_time"
        if schedule_type == "rolling":
            return "No fixed date / on request"

        if schedule_type == "recurring":
            parts: list[str] = []
            start_date_text = self._fmt_date(getattr(event, "start_date", None))
            if start_date_text:
                parts.append(f"Start {start_date_text}")

            occurrence_dates = self._parse_json_field(getattr(event, "occurrence_dates", None))
            if isinstance(occurrence_dates, list) and occurrence_dates:
                dates_text = [self._fmt_date(item) for item in occurrence_dates if item]
                dates_text = [item for item in dates_text if item]
                if dates_text:
                    parts.append(f"Dates: {', '.join(dates_text)}")
            else:
                recurring_rule = self._parse_json_field(getattr(event, "recurring_rule", None))
                if isinstance(recurring_rule, dict):
                    weekday_map = {
                        "MO": "monday",
                        "TU": "tuesday",
                        "WE": "wednesday",
                        "TH": "thursday",
                        "FR": "friday",
                        "SA": "saturday",
                        "SU": "sunday",
                    }
                    raw_positions = recurring_rule.get("bysetpos") or []
                    positions = []
                    for item in raw_positions:
                        try:
                            pos = int(item)
                        except Exception:
                            continue
                        if 1 <= pos <= 5:
                            positions.append(pos)
                    weekday = weekday_map.get(str(recurring_rule.get("byweekday") or "").upper(), "")
                    if positions or weekday:
                        pos_text = " and ".join(f"#{pos}" for pos in sorted(set(positions))) if positions else ""
                        parts.append(" ".join(part for part in (pos_text, weekday) if part).strip())

            time_text = self._time_range_text(getattr(event, "start_time", None), getattr(event, "end_time", None))
            if time_text:
                parts.append(time_text)
            return "; ".join(part for part in parts if part) or "Recurring schedule"

        starts_at = getattr(event, "starts_at", None)
        if starts_at is not None:
            return self._fmt_dt(starts_at)
        return "date TBD"

    def _event_prices_summary(self, event: Event) -> str:
        pricing_options = self._parse_json_field(getattr(event, "pricing_options", None))
        if isinstance(pricing_options, list) and pricing_options:
            parts: list[str] = []
            for item in pricing_options[:5]:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or "Price").strip() or "Price"
                price = item.get("price_rub")
                note = self._short(str(item.get("note") or ""), limit=80)
                if price in (None, ""):
                    chunk = f"{label}: on request"
                else:
                    chunk = f"{label}: {self._fmt_price(price)}"
                if note:
                    chunk += f" ({note})"
                parts.append(chunk)
            if parts:
                return "; ".join(parts)
        return f"Price: {self._fmt_price(getattr(event, 'price', None))}"

    def _event_detail_lines(self, event: Event) -> list[str]:
        lines = [f"- Title: {getattr(event, 'title', '')}"]
        lines.append(f"- Schedule: {self._event_schedule_summary(event)}")
        lines.append(f"- Location: {getattr(event, 'location', None) or 'online'}")
        lines.append(f"- Prices: {self._event_prices_summary(event)}")

        for label, value, limit in (
            ("Hosts", getattr(event, "hosts", None), 320),
            ("Description", getattr(event, "description", None), 360),
            ("Duration", getattr(event, "duration_hint", None), 220),
            ("Booking", getattr(event, "booking_hint", None), 220),
        ):
            text = self._short(value, limit=limit)
            if text:
                lines.append(f"- {label}: {text}")

        occurrence_dates = self._parse_json_field(getattr(event, "occurrence_dates", None))
        if isinstance(occurrence_dates, list) and occurrence_dates:
            dates_text = [self._fmt_date(item) for item in occurrence_dates if item]
            dates_text = [item for item in dates_text if item]
            if dates_text:
                lines.append(f"- Occurrence dates: {', '.join(dates_text)}")
        return lines

    async def _event_context(self, tg_id: int | None, limit: int = 10, query: str | None = None) -> tuple[str, dict[str, int]]:
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
                        lines.append("User events:")
                        for row in user_events:
                            lines.append(
                                f"- {row[0]} | {self._fmt_dt(row[1])} | {row[2] or 'online'} | {self._fmt_price(row[3])} | status: {row[4] or 'unknown'}"
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
                        lines.append("User consultations:")
                        for row in user_consults:
                            lines.append(
                                f"- {row[0]} ({row[1] or 'format not specified'}) | {self._fmt_price(row[2])} | {self._fmt_dt(row[4])} | status: {row[3] or 'unknown'}"
                            )

                active_events_rows = await session.execute(
                    select(Event)
                    .where(Event.is_active.is_(True))
                    .order_by(Event.updated_at.desc(), Event.id.desc())
                    .limit(min(limit, 10))
                )
                active_events = list(active_events_rows.scalars().all())
                counts["active_events"] = len(active_events)
                if active_events:
                    lines.append("Active events:")
                    for event in active_events[: min(limit, 5)]:
                        lines.append(
                            f"- {event.title} | {self._event_schedule_summary(event)} | {event.location or 'online'} | {self._event_prices_summary(event)}"
                        )

                    scored_events: list[tuple[int, Event]] = []
                    for event in active_events:
                        score = self._event_match_score(event, query)
                        if score > 0:
                            scored_events.append((score, event))
                    scored_events.sort(key=lambda item: item[0], reverse=True)
                    if scored_events:
                        lines.append("Relevant events (details):")
                        for _, event in scored_events[:3]:
                            lines.extend(self._event_detail_lines(event))

                catalog_rows = await session.execute(
                    select(CatalogItem.title, CatalogItem.price, CatalogItem.currency, CatalogItem.link_getcourse)
                    .where(CatalogItem.status == "active")
                    .order_by(CatalogItem.updated_at.desc(), CatalogItem.id.desc())
                    .limit(min(limit, 5))
                )
                catalog_items = list(catalog_rows.all())
                counts["catalog"] = len(catalog_items)
                if catalog_items:
                    lines.append("Catalog:")
                    for row in catalog_items:
                        lines.append(
                            f"- {row[0]} | {self._fmt_price(row[1], row[2] or 'RUB')} | link: {row[3] or 'pending'}"
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
                    lines.append("Recent GetCourse webhook events:")
                    for row in webhook_events:
                        lines.append(
                            f"- {row[0] or 'unknown'} | status: {row[1] or 'unknown'} | amount: {self._fmt_price(row[2], row[3] or 'RUB')} | {self._fmt_dt(row[4])}"
                        )

                return "\\n".join(lines).strip(), counts
        except Exception as e:
            logger.warning("Failed to build event context: %s", e.__class__.__name__)
            return "", counts

    def _parse_rag_focus(self, query: str) -> tuple[str, str]:
        raw = (query or "").strip()
        match = _RAG_FOCUS_PREFIX_RE.match(raw)
        if not match:
            return raw, "default"
        collection = (match.group("name") or "").strip().lower()
        cleaned = raw[match.end() :].lstrip() or raw
        return cleaned, collection or "default"

    def _rag_collection_dir(self, collection_name: str | None) -> str:
        registry = self._rag_collections_registry()
        name = (collection_name or "default").strip().lower() or "default"
        return registry.get(name) or registry.get("default") or self.rag_data_dir

    def _rag_collections_registry(self) -> dict[str, str]:
        if not self.rag_enabled or self.rag_retriever is None:
            return {"default": self.rag_data_dir}
        try:
            return self.rag_retriever.store.list_collections(self.rag_data_dir)
        except Exception as e:
            logger.warning("RAG collections discovery failed: %s", e.__class__.__name__)
            return {"default": self.rag_data_dir}

    def _rag_context(self, query: str) -> tuple[str, str, int]:
        context, confidence, chunks_count, _trace = self._rag_context_with_trace(query)
        return context, confidence, chunks_count

    def _rag_context_with_trace(self, query: str) -> tuple[str, str, int, dict[str, object]]:
        if not self.rag_enabled or self.rag_retriever is None:
            return "", "low", 0, {
                "rag_used": False,
                "rag_collection": "default",
                "rag_requested_collection": "default",
                "rag_hits": 0,
                "rag_top_scores": [],
                "rag_confidence": "low",
                "rag_fallback_to_default": False,
            }

        rag_query, collection_name = self._parse_rag_focus(query)
        registry = self._rag_collections_registry()
        requested_collection = (collection_name or "default").strip().lower() or "default"
        resolved_collection = requested_collection if requested_collection in registry else "default"
        collection_dir = registry.get(resolved_collection) or self.rag_data_dir
        trace: dict[str, object] = {
            "rag_used": False,
            "rag_collection": resolved_collection,
            "rag_requested_collection": requested_collection,
            "rag_hits": 0,
            "rag_top_scores": [],
            "rag_confidence": "low",
            "rag_fallback_to_default": requested_collection not in {"", "default"} and resolved_collection == "default",
        }

        try:
            result = self.rag_retriever.retrieve(
                query=rag_query,
                k=self.rag_top_k,
                min_score=self.rag_min_score,
                collection_dir=collection_dir,
            )
        except Exception as e:
            logger.warning("RAG retrieve failed: %s", e.__class__.__name__)
            return "", "low", 0, trace

        if not result.top_chunks and resolved_collection != "default":
            try:
                result = self.rag_retriever.retrieve(
                    query=rag_query,
                    k=self.rag_top_k,
                    min_score=self.rag_min_score,
                    collection_dir=registry.get("default") or self.rag_data_dir,
                )
                trace["rag_collection"] = "default"
                trace["rag_fallback_to_default"] = True
            except Exception as e:
                logger.warning("RAG retrieve fallback failed: %s", e.__class__.__name__)
                return "", "low", 0, trace

        trace["rag_confidence"] = result.confidence
        if not result.top_chunks:
            return "", result.confidence, 0, trace

        trace["rag_used"] = True
        trace["rag_hits"] = len(result.top_chunks)
        trace["rag_top_scores"] = [float(getattr(hit, "score", 0.0)) for hit in result.top_chunks[:3]]

        lines = ["???????? ???? ??????:"]
        for idx, chunk in enumerate(result.top_chunks, start=1):
            lines.append(
                f"{idx}. {chunk.title} ({chunk.source}, score={getattr(chunk, 'score', 0)}): {self._short(chunk.text, limit=520)}"
            )
        return self._trim_rag_context("\n".join(lines)), result.confidence, len(result.top_chunks), trace

    def get_last_trace(self) -> dict[str, object]:
        return dict(self._last_trace or {})

    def rag_debug_snapshot(self, query: str) -> dict:
        payload: dict[str, object] = {
            "enabled": bool(self.rag_enabled and self.rag_retriever is not None),
            "base_dir": self.rag_data_dir,
            "collections": {},
        }
        if not self.rag_enabled or self.rag_retriever is None:
            return payload

        store = self.rag_retriever.store
        collections = self._rag_collections_registry()
        payload["discovered_collections"] = sorted(collections.keys())
        _, _, _, trace = self._rag_context_with_trace(query)
        payload["trace"] = trace
        payload["last_response_trace"] = self.get_last_trace()
        for name, collection_dir in collections.items():
            try:
                docs = list(store._iter_files(collection_dir=collection_dir))
                chunks = store.load_chunks(collection_dir=collection_dir)
                result = self.rag_retriever.retrieve(
                    query=query,
                    k=min(3, self.rag_top_k),
                    min_score=self.rag_min_score,
                    collection_dir=collection_dir,
                )
                payload["collections"][name] = {
                    "dir": collection_dir,
                    "docs": len(docs),
                    "chunks": len(chunks),
                    "confidence": result.confidence,
                    "hits": [
                        {
                            "title": hit.title,
                            "source": hit.source,
                            "score": hit.score,
                            "text": self._short(hit.text, limit=280),
                        }
                        for hit in result.top_chunks[:3]
                    ],
                }
            except Exception as e:
                payload["collections"][name] = {
                    "dir": collection_dir,
                    "error": e.__class__.__name__,
                }
        return payload

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
        response_mode: str = "default",
    ) -> str:
        if not self.client:
            return self.UNAVAILABLE_MESSAGE

        clean_user_message = (user_message or "").replace("[SALES_MODE]", " ").strip()
        if not clean_user_message:
            clean_user_message = (user_message or "").strip()

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
            {"role": "system", "content": self._sales_guidance_prompt(user_message=user_message, response_mode=response_mode)},
        ]

        rag_confidence = "low"
        rag_chunks_count = 0
        event_context = ""
        rag_context = ""
        event_counts = {"user_events": 0, "consultations": 0, "active_events": 0, "catalog": 0, "webhooks": 0}
        rag_trace: dict[str, object] = {
            "rag_used": False,
            "rag_collection": "default",
            "rag_requested_collection": "default",
            "rag_hits": 0,
            "rag_top_scores": [],
            "rag_confidence": "low",
            "rag_fallback_to_default": False,
        }

        if include_events:
            event_context, event_counts = await self._event_context(tg_id=tg_id, limit=10, query=clean_user_message)
            if event_context:
                messages.append({"role": "system", "content": f"CRM and events context:\\n{event_context}"})
            rag_context, rag_confidence, rag_chunks_count, rag_trace = self._rag_context_with_trace(clean_user_message)
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

        self._last_trace = {
            "used_events": bool(event_context),
            "events_used": bool(event_context),
            "used_events_count": int(event_counts.get("active_events", 0) if isinstance(event_counts, dict) else 0),
            "events_count": int(event_counts.get("active_events", 0) if isinstance(event_counts, dict) else 0),
            "event_counts": event_counts,
            "rag_used": bool(rag_trace.get("rag_used")),
            "rag_collection": str(rag_trace.get("rag_collection") or "default"),
            "rag_used_collection": str(rag_trace.get("rag_collection") or "default"),
            "rag_requested_collection": str(rag_trace.get("rag_requested_collection") or "default"),
            "rag_hits": int(rag_trace.get("rag_hits", 0) or 0),
            "rag_top_scores": list(rag_trace.get("rag_top_scores") or []),
            "fallback_to_model": (not rag_context) or rag_confidence == "low",
            "rag_fallback_to_default": bool(rag_trace.get("rag_fallback_to_default")),
            "response_mode": response_mode,
        }

        if history:
            messages.extend(history[-10:])

        messages.append({"role": "user", "content": clean_user_message})
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
            self._last_trace["model_reply"] = True
            return content
        except Exception as e:
            logger.warning("AI request failed: %s", e.__class__.__name__)
            self._last_trace["model_error"] = e.__class__.__name__
            return "Извините, сейчас не получилось ответить. Попробуйте чуть позже."

    async def chat(
        self,
        user_message: str,
        chat_history: List[dict] | None = None,
        tg_id: int | None = None,
        response_mode: str = "default",
    ) -> Tuple[str, List[dict]]:
        response = await self.get_response(
            user_message=user_message,
            history=chat_history,
            include_events=True,
            tg_id=tg_id,
            response_mode=response_mode,
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
