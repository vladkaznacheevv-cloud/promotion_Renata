from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
        [InlineKeyboardButton("🎓 Консультации", callback_data="consultations")],
        [InlineKeyboardButton("🤖 AI-Ассистент", callback_data="ai_chat")],
        [InlineKeyboardButton("💎 VIP-Канал", callback_data="vip_channel")],
        [InlineKeyboardButton("📞 Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_events_keyboard(events):
    keyboard = []
    for event in events:
        keyboard.append([
            InlineKeyboardButton(
                f"{event.title} | {event.date.strftime('%d.%m')}", 
                callback_data=f"event_{event.id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard(payment_url: str):
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)