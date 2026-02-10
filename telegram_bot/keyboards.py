from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("Мероприятия", callback_data="events")],
        [InlineKeyboardButton("Онлайн-курсы", callback_data="courses")],
        [InlineKeyboardButton("Консультации", callback_data="consultations")],
        [InlineKeyboardButton("AI-ассистент", callback_data="ai_chat")],
        [InlineKeyboardButton("Оставить контакты", callback_data="share_contacts")],
        [InlineKeyboardButton("Связаться с менеджером", callback_data="contact_manager")],
        [InlineKeyboardButton("Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data="main_menu")]])


def get_consultations_menu():
    keyboard = [
        [InlineKeyboardButton("Форматы и цены", callback_data="consult_formats")],
        [InlineKeyboardButton("Спросить AI", callback_data="ai_chat")],
        [InlineKeyboardButton("В меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_consultation_formats_menu():
    keyboard = [
        [InlineKeyboardButton("Записаться (индивидуально)", callback_data="book_individual")],
        [InlineKeyboardButton("Записаться (группа)", callback_data="book_group")],
        [InlineKeyboardButton("Спросить AI", callback_data="ai_chat")],
        [InlineKeyboardButton("Назад", callback_data="consultations")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Повторить", callback_data="retry_db")]])


def get_event_actions_kb(event_id: int, registered: bool, link_getcourse: str | None = None):
    if registered:
        buttons = [[InlineKeyboardButton("Отменить запись", callback_data=f"event_cancel:{event_id}")]]
    else:
        buttons = [[InlineKeyboardButton("Записаться", callback_data=f"event_register:{event_id}")]]
    buttons.append([InlineKeyboardButton("Оплатить (YooKassa)", callback_data=f"event_pay:{event_id}")])
    if link_getcourse:
        buttons.append([InlineKeyboardButton("Открыть на GetCourse", url=link_getcourse)])
    buttons.append([InlineKeyboardButton("Связаться с менеджером", callback_data="contact_manager")])
    buttons.append([InlineKeyboardButton("В меню", callback_data="main_menu")])
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
