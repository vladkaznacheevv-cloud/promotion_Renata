from __future__ import annotations

import re
from typing import Literal

Intent = Literal["MENU", "MANAGER", "EVENTS", "COURSES", "CONSULT", "HELP", "GAME10"]

_SPACES_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z\u0410-\u042f\u0430-\u044f\u0401\u04510-9\s]")

_INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "MENU": ("\u043c\u0435\u043d\u044e", "\u0432 \u043c\u0435\u043d\u044e", "\u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e", "start"),
    "MANAGER": ("\u0441\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f \u0441 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u043e\u043c", "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440", "\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b", "\u0441\u0432\u044f\u0437\u044c", "\u0442\u0435\u043b\u0435\u0444\u043e\u043d"),
    "EVENTS": ("\u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f", "\u0437\u0430\u043f\u0438\u0441\u0430\u0442\u044c\u0441\u044f"),
    "COURSES": ("\u043e\u043d\u043b\u0430\u0439\u043d \u043a\u0443\u0440\u0441\u044b", "\u043a\u0443\u0440\u0441\u044b", "getcourse"),
    "CONSULT": ("\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u0438", "\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044f"),
    "HELP": ("\u043f\u043e\u043c\u043e\u0449\u044c", "help", "\u0447\u0442\u043e \u0443\u043c\u0435\u0435\u0448\u044c"),
    "GAME10": ("\u0438\u0433\u0440\u0430 10 0", "\u0438\u0433\u0440\u0430 10", "10 0", "\u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u043a\u0430\u043d\u0430\u043b", "\u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u043a\u043b\u0443\u0431"),
}

def _normalize_text(value: str) -> str:
    text = (value or "").lower().replace("\u0451", "\u0435")
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

    for intent in ("MENU", "MANAGER", "EVENTS", "COURSES", "CONSULT", "HELP", "GAME10"):
        phrases = _INTENT_KEYWORDS[intent]
        for phrase in phrases:
            if _contains_phrase(normalized, phrase):
                return intent
    return None
