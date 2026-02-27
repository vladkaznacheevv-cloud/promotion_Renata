from __future__ import annotations

import logging
import os
import re
from typing import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

logger = logging.getLogger(__name__)

_RUS_RE = re.compile(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]")
_MOJIBAKE_BIGRAM_RE = re.compile(r"(?:\u0420[\u0410-\u044FA-Za-z]|\u0421[\u0410-\u044FA-Za-z]|\u00D0.|\u00D1.)")
_MOJIBAKE_LATIN_RE = re.compile(r"[\u00D0\u00D1\u00C3]")
_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
_TRAILING_SPACES_RE = re.compile(r"[ \t]+\n")
_TOO_MANY_NEWLINES_RE = re.compile(r"\n{3,}")
_BAD_CYR_CHARS = set("\u0452\u0453\u0454\u0456\u0457\u0458\u0459\u045a\u045b\u045c\u045e\u045f")


def _score_text(value: str) -> int:
    if not value:
        return -10_000

    russian = len(_RUS_RE.findall(value))
    bad_bigram = len(_MOJIBAKE_BIGRAM_RE.findall(value))
    bad_latin = len(_MOJIBAKE_LATIN_RE.findall(value))
    bad_cyr = sum(1 for ch in value if ch in _BAD_CYR_CHARS)
    replacement = value.count("\ufffd") + value.count("????")
    return (russian * 8) - (bad_bigram * 12) - (bad_latin * 6) - (bad_cyr * 10) - (replacement * 20)


def looks_like_mojibake(text: str | None) -> bool:
    if not text:
        return False
    if "????" in text:
        return True
    if any(ch in text for ch in _BAD_CYR_CHARS):
        return True
    if _MOJIBAKE_BIGRAM_RE.search(text):
        return True
    if _MOJIBAKE_LATIN_RE.search(text) and len(_RUS_RE.findall(text)) < 3:
        return True
    return False


def _attempt_repairs(text: str) -> Iterable[str]:
    for source_encoding in ("cp1251", "latin1", "cp1252"):
        try:
            repaired = text.encode(source_encoding, errors="strict").decode("utf-8", errors="strict")
        except Exception:
            continue
        if repaired:
            yield repaired


def repair_mojibake(text: str | None) -> str | None:
    if text is None:
        return None
    if not looks_like_mojibake(text):
        return text

    best = text
    best_score = _score_text(text)
    for candidate in _attempt_repairs(text):
        score = _score_text(candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def render_text(text: str | None) -> str | None:
    if text is None:
        return None
    value = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _TRAILING_SPACES_RE.sub("\n", value)
    value = _TOO_MANY_NEWLINES_RE.sub("\n\n", value)
    return value


def normalize_telegram_text(text: str | None) -> str | None:
    if text is None:
        return None

    value = text
    try:
        value = value.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        pass

    value = _SURROGATE_RE.sub("", value)
    value = value.replace("\ufffd", "")
    return value


def normalize_ui_text(text: str | None) -> str | None:
    if text is None:
        return None

    source = normalize_telegram_text(str(text)) or str(text)
    if not looks_like_mojibake(source):
        return source

    best = source
    best_score = _score_text(source)
    for candidate in _attempt_repairs(source):
        score = _score_text(candidate)
        if score > best_score:
            best = candidate
            best_score = score

    best = best.replace("????", "")
    return normalize_telegram_text(best) or best


def normalize_text_for_telegram(text: str | None, *, label: str | None = None) -> str | None:
    if text is None:
        return None

    repaired = normalize_ui_text(text)
    rendered = render_text(repaired)
    rendered = normalize_telegram_text(rendered)

    if os.getenv("BOT_TEXT_DEBUG") == "1":
        marker = label or "text"
        logger.info(
            "text-debug %s: utf8_len=%s mojibake=%s",
            marker,
            len(text.encode("utf-8", errors="replace")),
            looks_like_mojibake(text),
        )
    return rendered


def normalize_ui_reply_markup(reply_markup):
    if reply_markup is None:
        return None
    try:
        if isinstance(reply_markup, InlineKeyboardMarkup):
            rows = []
            for row in reply_markup.inline_keyboard:
                normalized_row = []
                for button in row:
                    if not isinstance(button, InlineKeyboardButton):
                        normalized_row.append(button)
                        continue
                    normalized_row.append(
                        InlineKeyboardButton(
                            text=normalize_ui_text(button.text) or button.text,
                            url=button.url,
                            callback_data=button.callback_data,
                            switch_inline_query=button.switch_inline_query,
                            switch_inline_query_current_chat=button.switch_inline_query_current_chat,
                            callback_game=button.callback_game,
                            pay=button.pay,
                            login_url=button.login_url,
                            web_app=button.web_app,
                            switch_inline_query_chosen_chat=button.switch_inline_query_chosen_chat,
                            copy_text=button.copy_text,
                        )
                    )
                rows.append(normalized_row)
            return InlineKeyboardMarkup(rows)

        if isinstance(reply_markup, ReplyKeyboardMarkup):
            rows = []
            for row in reply_markup.keyboard:
                normalized_row = []
                for button in row:
                    if isinstance(button, KeyboardButton):
                        normalized_row.append(
                            KeyboardButton(
                                text=normalize_ui_text(button.text) or button.text,
                                request_contact=button.request_contact,
                                request_location=button.request_location,
                                request_poll=button.request_poll,
                                web_app=button.web_app,
                                request_user=button.request_user,
                                request_chat=button.request_chat,
                            )
                        )
                    else:
                        normalized_row.append(button)
                rows.append(normalized_row)
            return ReplyKeyboardMarkup(
                rows,
                resize_keyboard=reply_markup.resize_keyboard,
                one_time_keyboard=reply_markup.one_time_keyboard,
                selective=reply_markup.selective,
                input_field_placeholder=reply_markup.input_field_placeholder,
                is_persistent=reply_markup.is_persistent,
            )
    except Exception:
        return reply_markup
    return reply_markup
