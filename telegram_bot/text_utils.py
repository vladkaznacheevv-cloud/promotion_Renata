from __future__ import annotations

import logging
import os
import re
from typing import Iterable

logger = logging.getLogger(__name__)

_MOJIBAKE_PATTERNS: tuple[str, ...] = (
    "Ð",
    "Ñ",
    "Ã",
    "Рџ",
    "рџ",
    "Р°",
    "Рќ",
    "вЂ",
)

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_MOJIBAKE_LATIN_RE = re.compile(r"[ÐÑÃ]")


def _is_russian_cyrillic_char(ch: str) -> bool:
    code = ord(ch)
    return code == 0x401 or code == 0x451 or 0x410 <= code <= 0x44F


def _non_russian_cyrillic_count(value: str) -> int:
    count = 0
    for ch in value:
        code = ord(ch)
        if 0x0400 <= code <= 0x04FF and not _is_russian_cyrillic_char(ch):
            count += 1
    return count


def looks_like_mojibake(text: str | None) -> bool:
    if not text:
        return False
    if any(marker in text for marker in _MOJIBAKE_PATTERNS):
        return True
    if _MOJIBAKE_LATIN_RE.search(text):
        return True

    russian = len(_CYRILLIC_RE.findall(text))
    if russian > 0:
        rs_ratio = (text.count("Р") + text.count("С")) / max(1, russian)
        if rs_ratio > 0.35 and any(ch in text for ch in ("ѓ", "љ", "ќ", "џ", "ў")):
            return True
    return False


def _attempt_repairs(text: str) -> Iterable[str]:
    for source_encoding in ("cp1251", "latin1", "cp1252"):
        try:
            repaired = text.encode(source_encoding, errors="ignore").decode("utf-8", errors="ignore")
            if repaired:
                yield repaired
        except Exception:
            continue


def _score_text(value: str) -> int:
    if not value:
        return -10_000

    russian_count = len(_CYRILLIC_RE.findall(value))
    non_russian_cyr = _non_russian_cyrillic_count(value)
    mojibake_penalty = sum(value.count(marker) for marker in _MOJIBAKE_PATTERNS)
    latin_mojibake_penalty = len(_MOJIBAKE_LATIN_RE.findall(value))
    replacement_penalty = value.count("�")

    return (
        (russian_count * 10)
        - (non_russian_cyr * 25)
        - (mojibake_penalty * 60)
        - (latin_mojibake_penalty * 80)
        - (replacement_penalty * 100)
    )


def repair_mojibake(text: str | None) -> str | None:
    if text is None:
        return None
    if not looks_like_mojibake(text):
        return text

    best = text
    best_score = _score_text(text)
    frontier = {text}
    visited = {text}

    for _ in range(2):
        next_frontier = set()
        for current in frontier:
            for candidate in _attempt_repairs(current):
                if candidate in visited:
                    continue
                visited.add(candidate)
                next_frontier.add(candidate)
                score = _score_text(candidate)
                if score > best_score:
                    best = candidate
                    best_score = score
        if not next_frontier:
            break
        frontier = next_frontier

    return best


def normalize_text_for_telegram(text: str | None, *, label: str | None = None) -> str | None:
    if text is None:
        return None

    repaired = repair_mojibake(text)
    if os.getenv("BOT_TEXT_DEBUG") == "1":
        marker = label or "text"
        logger.info(
            "text-debug %s: repr=%r utf8_len=%s mojibake=%s",
            marker,
            text,
            len(text.encode("utf-8", errors="replace")),
            looks_like_mojibake(text),
        )
        if repaired != text:
            logger.info("text-debug %s repaired -> %r", marker, repaired)
    return repaired
