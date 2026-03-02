from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from telegram_bot.text_utils import normalize_ui_text

GETCOURSE_CABINET_URL = "https://renataminakova.ru"


def _ui(text: str) -> str:
    return normalize_ui_text(text) or text


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(_ui("«Игра 10:0»"), callback_data="private_channel")],
        [InlineKeyboardButton(_ui("Авторский курс лекций"), callback_data="courses")],
        [InlineKeyboardButton(_ui("Мероприятия"), callback_data="events")],
        [InlineKeyboardButton(_ui("Консультации"), callback_data="consultations")],
        [InlineKeyboardButton(_ui("Связаться с менеджером"), callback_data="contact_manager")],
        [InlineKeyboardButton(_ui("Помощь"), callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")]])


def get_consultations_menu():
    keyboard = [
        [InlineKeyboardButton(_ui("Форматы и цены"), callback_data="consult_formats")],
        [InlineKeyboardButton(_ui("Спросить ассистента"), callback_data="ai_chat")],
        [InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_consultation_formats_menu():
    keyboard = [
        [InlineKeyboardButton(_ui("Записаться (индивидуально)"), callback_data="book_individual")],
        [InlineKeyboardButton(_ui("Записаться (группа)"), callback_data="book_group")],
        [InlineKeyboardButton(_ui("Спросить ассистента"), callback_data="ai_chat")],
        [InlineKeyboardButton(_ui("Назад"), callback_data="consultations")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton(_ui("Повторить"), callback_data="retry_db")]])


def get_event_actions_kb(event_id: int, registered: bool, link_getcourse: str | None = None):
    _ = registered
    _ = link_getcourse
    buttons = [
        [InlineKeyboardButton(_ui("Записаться"), callback_data=f"event_register:{event_id}")],
        [InlineKeyboardButton(_ui("Вопросы к ассистенту"), callback_data="ai_chat")],
        [InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_contact_request_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(_ui("Отправить номер"), request_contact=True)],
            [KeyboardButton(_ui("Отмена"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_remove_reply_kb():
    return ReplyKeyboardRemove()


def get_courses_nav_kb(offset: int, limit: int, total: int):
    buttons = []
    row = []
    if offset > 0:
        prev_offset = max(offset - limit, 0)
        row.append(InlineKeyboardButton(_ui("Назад"), callback_data=f"courses_page:{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        row.append(InlineKeyboardButton(_ui("Следующие"), callback_data=f"courses_page:{next_offset}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_courses_empty_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(_ui("Открыть GetCourse"), url=GETCOURSE_CABINET_URL)],
            [InlineKeyboardButton(_ui("Ассистент расскажет о курсе / Задать вопросы"), callback_data="course_questions")],
            [InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")],
        ]
    )


def get_contact_manager_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(_ui("Оставить контакты"), callback_data="share_contacts")],
            [InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")],
        ]
    )


def get_private_channel_pending_kb(payment_url: str | None = None):
    buttons = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton(_ui("Оплатить 5 000 ₽"), url=payment_url)])
    else:
        buttons.append([InlineKeyboardButton(_ui("Оплатить 5 000 ₽"), callback_data="private_channel_payment_info")])
    buttons.append([InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_private_channel_paid_kb(invite_url: str | None = None):
    buttons = []
    if invite_url and invite_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton(_ui("Открыть ссылку"), url=invite_url)])
    buttons.append([InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_game10_kb(payment_url: str | None = None, *, show_test_payment: bool = False):
    rows = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(_ui("Оплатить 5 000 ₽"), url=payment_url)])
    else:
        rows.append([InlineKeyboardButton(_ui("Оплатить 5 000 ₽"), callback_data="private_channel_payment_info")])
    _ = show_test_payment  # legacy arg, button removed
    rows.append([InlineKeyboardButton(_ui("Описание программы"), callback_data="game10_description")])
    rows.append([InlineKeyboardButton(_ui("Вопросы к ассистенту"), callback_data="game10_questions")])
    rows.append([InlineKeyboardButton(_ui("В меню"), callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_game10_description_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(_ui("Обратно"), callback_data="private_channel")]]
    )


def get_payment_contact_choice_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(_ui("Поделиться телефоном"), callback_data="pay_contact_phone")],
            [InlineKeyboardButton(_ui("Ввести email"), callback_data="pay_contact_email")],
            [InlineKeyboardButton(_ui("Отмена"), callback_data="pay_contact_cancel")],
        ]
    )


def get_game10_payment_link_kb(
    confirmation_url: str,
    *,
    refresh_callback_data: str = "game10_pay_refresh",
    check_callback_data: str | None = None,
):
    rows = [[InlineKeyboardButton(_ui("Открыть оплату"), url=confirmation_url)]]
    if check_callback_data:
        rows.append([InlineKeyboardButton(_ui("✅ Я оплатил — проверить"), callback_data=check_callback_data)])
    rows.append([InlineKeyboardButton(_ui("Обновить ссылку"), callback_data=refresh_callback_data)])
    rows.append([InlineKeyboardButton(_ui("В меню"), callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_ai_quick_actions_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(_ui("Мероприятия"), callback_data="events"),
                InlineKeyboardButton(_ui("Консультации"), callback_data="consultations"),
            ],
            [
                InlineKeyboardButton(_ui("«Игра 10:0»"), callback_data="private_channel"),
                InlineKeyboardButton(_ui("Связаться"), callback_data="contact_manager"),
            ],
            [InlineKeyboardButton(_ui("В меню"), callback_data="main_menu")],
        ]
    )
