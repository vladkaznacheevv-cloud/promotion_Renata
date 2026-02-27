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


BAD_CHARS = set("\u0452\u0453\u0454\u0456\u0457\u0458\u0459\u045a\u045b\u045c\u045e\u045f")


def _make_mojibake(value: str) -> str:
    return value.encode("utf-8").decode("cp1251")


BAD_FRAGMENTS = tuple(
    _make_mojibake(ch) for ch in ("А", "В", "П", "с", "я", "т", "ш", "у")
) + ("????",)


def _assert_clean(value: str) -> None:
    assert value
    for token in BAD_FRAGMENTS:
        assert token not in value
    assert "????" not in value
    assert not any(ch in BAD_CHARS for ch in value)


def test_normalize_ui_text_repairs_common_mojibake():
    assert normalize_ui_text(_make_mojibake("В меню")) == "В меню"
    assert normalize_ui_text(_make_mojibake("Открыть GetCourse")) == "Открыть GetCourse"
    assert normalize_ui_text("Авторский курс лекций") == "Авторский курс лекций"


def test_normalize_ui_reply_markup_repairs_button_labels():
    broken = _make_mojibake("В меню")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(broken, callback_data="main_menu")]])
    normalized = normalize_ui_reply_markup(markup)
    assert normalized.inline_keyboard[0][0].text == "В меню"
    assert normalized.inline_keyboard[0][0].callback_data == "main_menu"


def test_keyboards_texts_are_clean_utf8():
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


def test_key_screen_texts_are_clean_after_normalization():
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
