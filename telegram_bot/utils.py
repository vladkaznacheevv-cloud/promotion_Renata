from __future__ import annotations

import re
from typing import Literal

Intent = Literal["MENU", "MANAGER", "EVENTS", "COURSES", "CONSULT"]

_SPACES_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Zа-яА-ЯёЁ0-9\s]")

_INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "MENU": ("меню", "в меню", "главное меню", "start"),
    "MANAGER": ("связаться с менеджером", "менеджер", "контакты", "связь", "телефон"),
    "EVENTS": ("мероприятия", "записаться"),
    "COURSES": ("онлайн курсы", "курсы", "getcourse"),
    "CONSULT": ("консультации", "консультация"),
}


def _normalize_text(value: str) -> str:
    text = (value or "").lower().replace("ё", "е")
    text = _NON_ALNUM_RE.sub(" ", text)
    return _SPACES_RE.sub(" ", text).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    if text == phrase:
        return True
    if text.startswith(f"{phrase} "):
        return True
    return f" {phrase} " in f" {text} "


def detect_intent(text: str | None) -> Intent | None:
    normalized = _normalize_text(text or "")
    if not normalized:
        return None

    for intent in ("MENU", "MANAGER", "EVENTS", "COURSES", "CONSULT"):
        phrases = _INTENT_KEYWORDS[intent]
        for phrase in phrases:
            if _contains_phrase(normalized, phrase):
                return intent
    return None
