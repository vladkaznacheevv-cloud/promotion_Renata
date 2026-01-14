import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters
)
from telegram.error import TelegramError
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ============ КОНФИГ ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_ASSISTANT_NAME = os.getenv("AI_ASSISTANT_NAME", "Mimo")

# ============ AI-КЛИЕНТ ============
class AIClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://api.xiaomimimo.com/v1"
        )
        self.system_prompt = (
            "Ты дружелюбный ассистент проекта Renata Promotion. "
            "Отвечай кратко, по делу и вежливо."
        )
    
    async def get_response(self, user_message: str, history: list = None) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model="mimo-v2-flash",
                messages=messages,
                max_completion_tokens=1024,
                temperature=0.3,
                top_p=0.95,
                extra_body={
                    "thinking": {"type": "disabled"}
                }
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Ошибка AI: {str(e)}"

ai_client = AIClient()
chat_histories = {}

# ============ КЛАВИАТУРЫ ============
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
        [InlineKeyboardButton("🤖 AI-Ассистент", callback_data="ai_chat")],
        [InlineKeyboardButton("💎 VIP-Канал", callback_data="vip_channel")],
        [InlineKeyboardButton("📞 Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_events_keyboard():
    events = [
        {"id": 1, "title": "🎵 Концерт 'Ностальгия'", "date": "25 янв", "price": "1000₽"},
        {"id": 2, "title": "🎓 Мастер-класс SMM", "date": "1 фев", "price": "Бесплатно"},
        {"id": 3, "title": "🎨 Арт-вечеринка", "date": "15 янв", "price": "500₽"},
    ]
    keyboard = []
    for event in events:
        keyboard.append([InlineKeyboardButton(
            f"{event['title']} | {event['date']}", 
            callback_data=f"event_{event['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 500₽", callback_data="pay_500")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_vip_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔗 Вступить в канал", url="https://t.me/+XXXXX")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ============ МЕРОПРИЯТИЯ ============
EVENTS_DATA = {
    1: {"title": "🎵 Концерт 'Ностальгия'", "desc": "Вечер хитов 90-х", "date": "25 января", "loc": "Клуб 'Метро'", "price": "1000₽"},
    2: {"title": "🎓 Мастер-класс SMM", "desc": "Обучение продвижению", "date": "1 февраля", "loc": "Онлайн", "price": "Бесплатно"},
    3: {"title": "🎨 Арт-вечеринка", "desc": "Рисование и музыка", "date": "15 января", "loc": "Галерея 'Арт'", "price": "500₽"},
}

# ============ ХЕНДЛЕРЫ ============
# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🎉 Привет, {user.first_name}!\n\n"
        "Я — бот проекта Renata Promotion.\n\n"
        "📅 Мероприятия\n"
        "🤖 AI-помощник\n"
        "💎 VIP-канал\n\n"
        "Выбери раздел 👇"
    )
    await update.message.reply_text(text, reply_markup=get_main_menu())

# Главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()  # СРАЗУ отвечаем!
    except:
        pass
    try:
        await query.edit_message_text("📋 Главное меню", reply_markup=get_main_menu())
    except:
        pass

# Мероприятия
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        text = "📅 *Ближайшие мероприятия*\n\n"
        for e in EVENTS_DATA.values():
            text += f"*{e['title']}* — {e['date']} ({e['price']})\n"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_events_keyboard())
    except:
        pass

# Детали мероприятия
async def event_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        event_id = int(query.data.split('_')[1])
        e = EVENTS_DATA.get(event_id)
        if e:
            text = f"*{e['title']}*\n\n{e['desc']}\n\n📆 {e['date']}\n📍 {e['loc']}\n💰 {e['price']}"
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_events_keyboard())
    except:
        pass

# AI-Ассистент
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        user_id = update.effective_user.id
        chat_histories[user_id] = []
        await query.edit_message_text(
            f"🤖 *{AI_ASSISTANT_NAME}* готов!\n\nНапиши вопрос, отвечу на всё.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
    except:
        pass

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if user_message.startswith('/'):
        return
    
    # Сначала скажем "печатает..."
    await update.message.reply_text("🤖 Mimo печатает...")
    
    history = chat_histories.get(user_id, [])
    ai_response = await ai_client.get_response(user_message, history)
    history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": ai_response}])
    chat_histories[user_id] = history
    
    await update.message.reply_text(ai_response)

# VIP-канал
async def vip_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        await query.edit_message_text(
            "💎 *VIP-Канал*\n\n"
            "Эксклюзивный контент, закрытые мероприятия, общение с организаторами.\n\n"
            "Стоимость: 500₽/месяц",
            parse_mode='Markdown',
            reply_markup=get_payment_keyboard()
        )
    except:
        pass

# Оплата (заглушка)
async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        await query.edit_message_text(
            "💳 *Оплата*\n\n"
            "Переход в ЮKassa...\n\n"
            "(В разработке)",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
    except:
        pass

# Помощь
async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    try:
        text = """
📚 *Справка*

• /start — запустить
• /menu — меню

📅 Мероприятия — расписание
🤖 AI — задай вопрос
💎 VIP — оплата доступа

❓ support@renata.ru
"""
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_menu())
    except:
        pass

# ============ MAIN ============
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавь эту строку!
    await app.initialize()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CommandHandler("help", help_menu))
    
    # Коллбэки
    app.add_handler(CallbackQueryHandler(main_menu, pattern="main_menu"))
    app.add_handler(CallbackQueryHandler(events, pattern="events"))
    app.add_handler(CallbackQueryHandler(event_detail, pattern="event_"))
    app.add_handler(CallbackQueryHandler(ai_chat, pattern="ai_chat"))
    app.add_handler(CallbackQueryHandler(vip_channel, pattern="vip_channel"))
    app.add_handler(CallbackQueryHandler(payment, pattern="pay_"))
    app.add_handler(CallbackQueryHandler(help_menu, pattern="help"))
    
    # AI-сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
    
    print("🚀 Бот запущен...")
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())