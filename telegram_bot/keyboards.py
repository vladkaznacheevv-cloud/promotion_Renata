from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
        [InlineKeyboardButton("🎓 Консультации", callback_data="consultations")],
        [InlineKeyboardButton("🤖 AI-Ассистент", callback_data="ai_chat")],
        [InlineKeyboardButton("📞 Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="main_menu")]])


def get_consultations_menu():
    # Экран 1 → выбор: форматы/цены или AI
    keyboard = [
        [InlineKeyboardButton("🎓 Форматы и цены", callback_data="consult_formats")],
        [InlineKeyboardButton("🤖 Спросить AI", callback_data="ai_chat")],
        [InlineKeyboardButton("🔙 В меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_consultation_formats_menu():
    # Экран 2 → записаться
    keyboard = [
        [InlineKeyboardButton("📅 Записаться (индивидуально)", callback_data="book_individual")],
        [InlineKeyboardButton("📅 Записаться (группа)", callback_data="book_group")],
        [InlineKeyboardButton("🤖 Спросить AI", callback_data="ai_chat")],
        [InlineKeyboardButton("🔙 Назад", callback_data="consultations")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Повторить", callback_data="retry_db")]])
