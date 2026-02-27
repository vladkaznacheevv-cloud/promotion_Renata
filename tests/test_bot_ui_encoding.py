from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot import main as bot_main
from telegram_bot.keyboards import (
    get_back_to_menu_kb,
    get_consultations_menu,
    get_contact_request_kb,
    get_courses_empty_kb,
    get_game10_kb,
    get_game10_payment_link_kb,
    get_main_menu,
)
from telegram_bot.text_utils import normalize_ui_reply_markup, normalize_ui_text


BAD_UNICODE_CHARS = set("\u0452\u0453\u0454\u0456\u0457\u0458\u0459\u045a\u045b\u045c\u045e\u045f")
BAD_FRAGMENTS = (
    "\u0420\u045f",
    "\u0420\u2019",
    "\u0420\u0178",
    "\u0421\u0455",
    "\u0421\u040f",
    "\u0421\u201a",
    "\u0421\u20ac",
    "\u0421\u0453",
    "????",
)


def _make_mojibake(value: str) -> str:
    return value.encode("utf-8").decode("cp1251")


def _assert_clean(value: str) -> None:
    assert value
    for token in BAD_FRAGMENTS:
        assert token not in value
    assert "????" not in value
    assert not any(ch in BAD_UNICODE_CHARS for ch in value)


def test_normalize_ui_text_repairs_common_mojibake() -> None:
    assert normalize_ui_text(_make_mojibake("\u0412 \u043c\u0435\u043d\u044e")) == "\u0412 \u043c\u0435\u043d\u044e"
    assert normalize_ui_text(_make_mojibake("\u041e\u0442\u043a\u0440\u044b\u0442\u044c GetCourse")) == "\u041e\u0442\u043a\u0440\u044b\u0442\u044c GetCourse"
    assert normalize_ui_text("\u0410\u0432\u0442\u043e\u0440\u0441\u043a\u0438\u0439 \u043a\u0443\u0440\u0441 \u043b\u0435\u043a\u0446\u0438\u0439") == "\u0410\u0432\u0442\u043e\u0440\u0441\u043a\u0438\u0439 \u043a\u0443\u0440\u0441 \u043b\u0435\u043a\u0446\u0438\u0439"


def test_normalize_ui_reply_markup_repairs_button_labels() -> None:
    broken = _make_mojibake("\u0412 \u043c\u0435\u043d\u044e")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(broken, callback_data="main_menu")]])
    normalized = normalize_ui_reply_markup(markup)
    assert normalized.inline_keyboard[0][0].text == "\u0412 \u043c\u0435\u043d\u044e"
    assert normalized.inline_keyboard[0][0].callback_data == "main_menu"


def test_keyboards_texts_are_clean_utf8() -> None:
    inline_markups = [
        get_main_menu(),
        get_back_to_menu_kb(),
        get_consultations_menu(),
        get_courses_empty_kb(),
        get_game10_kb(),
        get_game10_payment_link_kb("https://example.com", check_callback_data="game10_pay_check:x"),
    ]
    for markup in inline_markups:
        for row in markup.inline_keyboard:
            for button in row:
                _assert_clean(button.text)

    reply_markup = get_contact_request_kb()
    for row in reply_markup.keyboard:
        for button in row:
            _assert_clean(button.text)


def test_key_screen_texts_are_clean_after_normalization() -> None:
    key_texts = [
        bot_main.GAME10_SCREEN_TEXT,
        bot_main.GAME10_DESCRIPTION_SCREEN_TEXT,
        bot_main.PAYMENT_NEED_CONTACT_SCREEN,
        bot_main.PAYMENT_STATUS_CONFIRMED_SCREEN,
        bot_main.PAYMENT_STATUS_CANCELED_SCREEN,
    ]
    for value in key_texts:
        normalized = normalize_ui_text(value) or ""
        _assert_clean(normalized)
