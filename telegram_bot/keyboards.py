from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

GETCOURSE_CABINET_URL = "https://renataminakova.getcourse.ru/"


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("«Игра 10:0»", callback_data="private_channel")],
        [InlineKeyboardButton("Авторский курс лекций", callback_data="courses")],
        [InlineKeyboardButton("Мероприятия", callback_data="events")],
        [InlineKeyboardButton("Консультации", callback_data="consultations")],
        [InlineKeyboardButton("Связаться с менеджером", callback_data="contact_manager")],
        [InlineKeyboardButton("Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")]])


def get_consultations_menu():
    keyboard = [
        [InlineKeyboardButton("Р¤РѕСЂРјР°С‚С‹ Рё С†РµРЅС‹", callback_data="consult_formats")],
        [InlineKeyboardButton("РЎРїСЂРѕСЃРёС‚СЊ Р°СЃСЃРёСЃС‚РµРЅС‚Р°", callback_data="ai_chat")],
        [InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_consultation_formats_menu():
    keyboard = [
        [InlineKeyboardButton("Р—Р°РїРёСЃР°С‚СЊСЃСЏ (РёРЅРґРёРІРёРґСѓР°Р»СЊРЅРѕ)", callback_data="book_individual")],
        [InlineKeyboardButton("Р—Р°РїРёСЃР°С‚СЊСЃСЏ (РіСЂСѓРїРїР°)", callback_data="book_group")],
        [InlineKeyboardButton("РЎРїСЂРѕСЃРёС‚СЊ Р°СЃСЃРёСЃС‚РµРЅС‚Р°", callback_data="ai_chat")],
        [InlineKeyboardButton("РќР°Р·Р°Рґ", callback_data="consultations")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("РџРѕРІС‚РѕСЂРёС‚СЊ", callback_data="retry_db")]])


def get_event_actions_kb(event_id: int, registered: bool, link_getcourse: str | None = None):
    _ = registered
    _ = link_getcourse
    buttons = [
        [InlineKeyboardButton("Р—Р°РїРёСЃР°С‚СЊСЃСЏ", callback_data=f"event_register:{event_id}")],
        [InlineKeyboardButton("Р’РѕРїСЂРѕСЃС‹ Рє Р°СЃСЃРёСЃС‚РµРЅС‚Сѓ", callback_data="ai_chat")],
        [InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_contact_request_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("РћС‚РїСЂР°РІРёС‚СЊ РЅРѕРјРµСЂ", request_contact=True)],
            [KeyboardButton("РћС‚РјРµРЅР°")],
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
        row.append(InlineKeyboardButton("РќР°Р·Р°Рґ", callback_data=f"courses_page:{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        row.append(InlineKeyboardButton("РЎР»РµРґСѓСЋС‰РёРµ", callback_data=f"courses_page:{next_offset}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_courses_empty_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("РћС‚РєСЂС‹С‚СЊ GetCourse", url=GETCOURSE_CABINET_URL)],
            [InlineKeyboardButton("РђСЃСЃРёСЃС‚РµРЅС‚ СЂР°СЃСЃРєР°Р¶РµС‚ Рѕ РєСѓСЂСЃРµ / Р—Р°РґР°С‚СЊ РІРѕРїСЂРѕСЃС‹", callback_data="course_questions")],
            [InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")],
        ]
    )


def get_contact_manager_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("РћСЃС‚Р°РІРёС‚СЊ РєРѕРЅС‚Р°РєС‚С‹", callback_data="share_contacts")],
            [InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")],
        ]
    )


def get_private_channel_pending_kb(payment_url: str | None = None):
    buttons = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton("РћРїР»Р°С‚РёС‚СЊ 5 000 в‚Ѕ", url=payment_url)])
    else:
        buttons.append([InlineKeyboardButton("РћРїР»Р°С‚РёС‚СЊ 5 000 в‚Ѕ", callback_data="private_channel_payment_info")])
    buttons.append([InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_private_channel_paid_kb(invite_url: str | None = None):
    buttons = []
    if invite_url and invite_url.startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton("РћС‚РєСЂС‹С‚СЊ СЃСЃС‹Р»РєСѓ", url=invite_url)])
    buttons.append([InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_game10_kb(payment_url: str | None = None, *, show_test_payment: bool = False):
    rows = []
    if payment_url and payment_url.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton("РћРїР»Р°С‚РёС‚СЊ 5 000 в‚Ѕ", url=payment_url)])
    else:
        rows.append([InlineKeyboardButton("РћРїР»Р°С‚РёС‚СЊ 5 000 в‚Ѕ", callback_data="private_channel_payment_info")])
    _ = show_test_payment  # legacy arg, button removed
    rows.append([InlineKeyboardButton("РћРїРёСЃР°РЅРёРµ РїСЂРѕРіСЂР°РјРјС‹", callback_data="game10_description")])
    rows.append([InlineKeyboardButton("Р’РѕРїСЂРѕСЃС‹ Рє Р°СЃСЃРёСЃС‚РµРЅС‚Сѓ", callback_data="game10_questions")])
    rows.append([InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_game10_description_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("РћР±СЂР°С‚РЅРѕ", callback_data="private_channel")]]
    )


def get_payment_contact_choice_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("РџРѕРґРµР»РёС‚СЊСЃСЏ С‚РµР»РµС„РѕРЅРѕРј", callback_data="pay_contact_phone")],
            [InlineKeyboardButton("Р’РІРµСЃС‚Рё email", callback_data="pay_contact_email")],
            [InlineKeyboardButton("РћС‚РјРµРЅР°", callback_data="pay_contact_cancel")],
        ]
    )


def get_game10_payment_link_kb(
    confirmation_url: str,
    *,
    refresh_callback_data: str = "game10_pay_refresh",
    check_callback_data: str | None = None,
):
    rows = [[InlineKeyboardButton("РћС‚РєСЂС‹С‚СЊ РѕРїР»Р°С‚Сѓ", url=confirmation_url)]]
    if check_callback_data:
        rows.append([InlineKeyboardButton("РџСЂРѕРІРµСЂРёС‚СЊ РѕРїР»Р°С‚Сѓ", callback_data=check_callback_data)])
    rows.append([InlineKeyboardButton("РћР±РЅРѕРІРёС‚СЊ СЃСЃС‹Р»РєСѓ", callback_data=refresh_callback_data)])
    rows.append([InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def get_ai_quick_actions_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("РњРµСЂРѕРїСЂРёСЏС‚РёСЏ", callback_data="events"),
                InlineKeyboardButton("РљРѕРЅСЃСѓР»СЊС‚Р°С†РёРё", callback_data="consultations"),
            ],
            [
                InlineKeyboardButton("В«РРіСЂР° 10:0В»", callback_data="private_channel"),
                InlineKeyboardButton("РЎРІСЏР·Р°С‚СЊСЃСЏ", callback_data="contact_manager"),
            ],
            [InlineKeyboardButton("Р’ РјРµРЅСЋ", callback_data="main_menu")],
        ]
    )

