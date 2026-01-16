import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv

# Core сервисы
from core.database import async_session
from core.users.service import UserService
from core.events.service import EventService
from core.ai.ai_service import AIService
from core.payments.service import PaymentService
from core.analytics.service import AnalyticsService

from telegram_bot.keyboards import get_main_menu, get_events_keyboard

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "mimo-v2-flash")

# Инициализация сервисов
ai_service = AIService(api_key=AI_API_KEY, model=AI_MODEL)
chat_histories = {}

# ============ Хендлеры ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    async with async_session() as session:
        user_service = UserService(session)
        
        # Создаём/обновляем пользователя
        from core.users.schemas import UserCreate
        await user_service.get_or_create(
            UserCreate(
                tg_id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username,
                source='bot'
            )
        )
    
    text = (
        f"🎉 Привет, {user.first_name}!\n\n"
        "Renata Promotion — твой проводник в мир мероприятий!\n\n"
        "📅 Мероприятия\n"
        "🎓 Консультации\n"
        "🤖 AI-помощник\n"
        "💎 VIP-канал\n\n"
        "Выбери раздел 👇"
    )
    await update.message.reply_text(text, reply_markup=get_main_menu())


async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        event_service = EventService(session)
        events = await event_service.get_active()
        
        if not events:
            text = "📅 Скоро появятся новые мероприятия!"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
        else:
            text = "📅 *Ближайшие мероприятия*\n\n"
            for event in events:
                text += f"• {event.title} — {event.date.strftime('%d.%m в %H:%M')}\n"
            keyboard = get_events_keyboard(events)
        
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')


async def show_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    
    await query.edit_message_text(
        "🤖 *Mimo* готов ответить на твои вопросы!\n\n"
        "Напиши что тебя интересует — о мероприятиях, консультациях или VIP-канале.",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if user_message.startswith('/'):
        return
    
    history = chat_histories.get(user_id, [])
    response, new_history = await ai_service.chat(user_message, history)
    chat_histories[user_id] = new_history
    
    await update.message.reply_text(response)


async def show_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить 500₽", callback_data="pay_vip")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ])
    
    await query.edit_message_text(
        "💎 *VIP-Канал*\n\n"
        "Эксклюзивный контент, закрытые мероприятия, общение с организаторами.\n\n"
        "500₽/месяц",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = """
📚 *Помощь*

• /start — перезапуск бота
• Напиши мне — получу ответ

📅 Мероприятия — расписание
🎓 Консультации — запись
🤖 AI — задай вопрос
💎 VIP — доступ к каналу

📧 support@renata.ru
    """
    await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='Markdown')


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📋 Главное меню", reply_markup=get_main_menu())


# ============ MAIN ============
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", main_menu))
    
    # Коллбэки
    app.add_handler(CallbackQueryHandler(main_menu, pattern="main_menu"))
    app.add_handler(CallbackQueryHandler(show_events, pattern="events"))
    app.add_handler(CallbackQueryHandler(show_ai_chat, pattern="ai_chat"))
    app.add_handler(CallbackQueryHandler(show_vip, pattern="vip_channel"))
    app.add_handler(CallbackQueryHandler(show_help, pattern="help"))
    
    # AI сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
    
    logger.info("🚀 Renata Bot запущен!")
    print("🚀 Renata Bot запущен!")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())