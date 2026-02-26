from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

GETCOURSE_CABINET_URL = "https://renataminakova.getcourse.ru"


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("\u00ab\u0418\u0433\u0440\u0430 10:0\u00bb", callback_data="private_channel")],
        [InlineKeyboardButton("\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f", callback_data="events")],
        [InlineKeyboardButton("\u041e\u043d\u043b\u0430\u0439\u043d-\u043a\u0443\u0440\u0441\u044b", callback_data="courses")],
        [InlineKeyboardButton("\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u0438", callback_data="consultations")],
        [InlineKeyboardButton("\u0421\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f \u0441 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u043e\u043c", callback_data="contact_manager")],
        [InlineKeyboardButton("\u041f\u043e\u043c\u043e\u0449\u044c", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data="main_menu")]])


def get_consultations_menu():
    keyboard = [
        [InlineKeyboardButton("Форматы и цены", callback_data="consult_formats")],
        [InlineKeyboardButton("Спросить ассистента", callback_data="ai_chat")],
        [InlineKeyboardButton("В меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_consultation_formats_menu():
    keyboard = [
        [InlineKeyboardButton("Записаться (индивидуально)", callback_data="book_individual")],
        [InlineKeyboardButton("Записаться (группа)", callback_data="book_group")],
        [InlineKeyboardButton("Спросить ассистента", callback_data="ai_chat")],
        [InlineKeyboardButton("Назад", callback_data="consultations")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Повторить", callback_data="retry_db")]])


def get_event_actions_kb(event_id: int, registered: bool, link_getcourse: str | None = None):
    _ = registered
    _ = link_getcourse
    buttons = [
        [InlineKeyboardButton("Записаться", callback_data=f"event_register:{event_id}")],
        [InlineKeyboardButton("Вопросы к ассистенту", callback_data="ai_chat")],
        [InlineKeyboardButton("В меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_contact_request_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Отправить номер", request_contact=True)],
            [KeyboardButton("Отмена")],
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
        row.append(InlineKeyboardButton("Назад", callback_data=f"courses_page:{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        row.append(InlineKeyboardButton("Следующие", callback_data=f"courses_page:{next_offset}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_courses_empty_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Открыть GetCourse", url=GETCOURSE_CABINET_URL)],
            [InlineKeyboardButton("Ассистент расскажет о курсе / Задать вопросы", callback_data="course_questions")],
            [InlineKeyboardButton("В меню", callback_data="main_menu")],
        ]
    )


def get_contact_manager_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Оставить контакты", callback_data="share_contacts")],
            [InlineKeyboardButton("В меню", callback_data="main_menu")],
        ]
    )


def get_private_channel_pending_kb(payment_url: str | None = None):
    buttons = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton("Оплатить 5 000 ₽", url=payment_url)])
    else:
        buttons.append([InlineKeyboardButton("Оплатить 5 000 ₽", callback_data="private_channel_payment_info")])
    buttons.append([InlineKeyboardButton("В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_private_channel_paid_kb(invite_url: str | None = None):
    buttons = []
    if invite_url and invite_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton("Открыть ссылку", url=invite_url)])
    buttons.append([InlineKeyboardButton("В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_game10_kb(payment_url: str | None = None, *, show_test_payment: bool = False):
    rows = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton("Оплатить 5 000 ₽", url=payment_url)])
    else:
        rows.append([InlineKeyboardButton("Оплатить 5 000 ₽", callback_data="private_channel_payment_info")])
    if show_test_payment:
        rows.append([InlineKeyboardButton("Тестовая оплата 50 ₽", callback_data="game10_pay_test")])
    rows.append([InlineKeyboardButton("Описание программы", callback_data="game10_description")])
    rows.append([InlineKeyboardButton("Вопросы к ассистенту", callback_data="game10_questions")])
    rows.append([InlineKeyboardButton("В меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_game10_description_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Обратно", callback_data="private_channel")]]
    )


def get_payment_contact_choice_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Поделиться телефоном", callback_data="pay_contact_phone")],
            [InlineKeyboardButton("Ввести email", callback_data="pay_contact_email")],
            [InlineKeyboardButton("Отмена", callback_data="pay_contact_cancel")],
        ]
    )


def get_game10_payment_link_kb(
    confirmation_url: str,
    *,
    refresh_callback_data: str = "game10_pay_refresh",
    check_callback_data: str | None = None,
):
    rows = [[InlineKeyboardButton("Открыть оплату", url=confirmation_url)]]
    if check_callback_data:
        rows.append([InlineKeyboardButton("Проверить оплату", callback_data=check_callback_data)])
    rows.append([InlineKeyboardButton("Обновить ссылку", callback_data=refresh_callback_data)])
    rows.append([InlineKeyboardButton("В меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_ai_quick_actions_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f", callback_data="events"),
                InlineKeyboardButton("\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u0438", callback_data="consultations"),
            ],
            [
                InlineKeyboardButton("\u00ab\u0418\u0433\u0440\u0430 10:0\u00bb", callback_data="private_channel"),
                InlineKeyboardButton("\u0421\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f", callback_data="contact_manager"),
            ],
            [InlineKeyboardButton("\u0412 \u043c\u0435\u043d\u044e", callback_data="main_menu")],
        ]
    )
