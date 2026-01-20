import os
import logging
import core.models  # важно: регистрирует модели для SQLAlchemy, если где-то есть create_all

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Core
from core.database import async_session
from core.users.service import UserService
from core.events.service import EventService
from core.ai.ai_service import AIService

# Keyboards
from telegram_bot.keyboards import (
    get_main_menu,
    get_back_to_menu_kb,
    get_consultations_menu,
    get_consultation_formats_menu,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "mimo-v2-flash")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # опционально

# Services
ai_service = AIService(api_key=AI_API_KEY, model=AI_MODEL)

# In-memory (позже можно вынести историю в Redis/DB)
chat_histories: dict[int, list[dict]] = {}

# User states
WAITING_LEAD_KEY = "waiting_lead"  # None | "individual" | "group"
AI_MODE_KEY = "ai_mode"            # bool


# ======= Контент (ультра-коротко, 1–2 экрана) =======
GESTALT_SHORT_SCREEN_1 = (
    "🧠 *Гештальт-терапия*\n\n"
    "Помогает:\n"
    "• лучше понимать свои чувства\n"
    "• снижать внутреннее напряжение\n"
    "• жить осознанно «здесь и сейчас»\n\n"
    "Это про живой контакт с собой и людьми,\n"
    "а не про советы «как правильно»."
)

GESTALT_SHORT_SCREEN_2 = (
    "🎓 *Форматы и цены*\n\n"
    "👤 *Индивидуальная терапия*\n"
    "Личное пространство для работы с собой.\n"
    "💰 Цена: *уточняется при записи*\n\n"
    "👥 *Групповая терапия*\n"
    "Безопасная группа для поддержки и опыта.\n"
    "💰 Цена: *уточняется при записи*\n\n"
    "В процессе вы:\n"
    "– лучше понимаете себя\n"
    "– учитесь выстраивать границы\n"
    "– становитесь свободнее и честнее"
)

AI_HINT = (
    "🤖 *Mimo* готов помочь.\n\n"
    "Задай вопрос — про мероприятия, консультации или VIP."
)


# ============ Helpers ============

def _reset_states(context: ContextTypes.DEFAULT_TYPE):
    context.user_data[WAITING_LEAD_KEY] = None
    context.user_data[AI_MODE_KEY] = False


async def ensure_user(update: Update, source: str = "bot"):
    """
    Единая точка: создаём/обновляем пользователя в БД по tg_id.
    Возвращает объект User (из БД).
    """
    tg_user = update.effective_user
    if tg_user is None:
        return None

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_by_tg_id(
            tg_id=tg_user.id,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            username=tg_user.username,
            source=source,
            update_if_exists=True,
        )
        await session.commit()
        return user


# ============ Handlers ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # гарантируем наличие user в БД
    user_db = await ensure_user(update, source="bot")

    _reset_states(context)

    tg_user = update.effective_user
    name = (tg_user.first_name if tg_user else None) or (user_db.first_name if user_db else "друг")

    text = (
        f"🎉 Привет, {name}!\n\n"
        "Renata Promotion — бот про мероприятия и терапию.\n\n"
        "Выбери раздел 👇"
    )
    await update.message.reply_text(text, reply_markup=get_main_menu())


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _reset_states(context)
    await query.edit_message_text("📋 Главное меню", reply_markup=get_main_menu())


# --------- Events ---------

async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _reset_states(context)

    # опционально: фиксируем пользователя и здесь тоже
    await ensure_user(update, source="bot")

    async with async_session() as session:
        event_service = EventService(session)
        events = await event_service.list_active()  # было get_active()

    if not events:
        await query.edit_message_text("📅 Скоро появятся новые мероприятия!", reply_markup=get_back_to_menu_kb())
        return

    text = "📅 *Ближайшие мероприятия*\n\n"
    for event in events:
        # у тебя в БД starts_at/ends_at, поэтому используем starts_at
        if event.starts_at:
            text += f"• {event.title} — {event.starts_at.strftime('%d.%m в %H:%M')}\n"
        else:
            text += f"• {event.title}\n"

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_back_to_menu_kb())


# --------- Consultations / Gestalt ---------

async def show_consultations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _reset_states(context)

    await ensure_user(update, source="bot")

    await query.edit_message_text(
        GESTALT_SHORT_SCREEN_1,
        parse_mode="Markdown",
        reply_markup=get_consultations_menu(),
    )


async def show_formats_and_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _reset_states(context)

    await ensure_user(update, source="bot")

    await query.edit_message_text(
        GESTALT_SHORT_SCREEN_2,
        parse_mode="Markdown",
        reply_markup=get_consultation_formats_menu(),
    )


async def begin_booking_individual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[AI_MODE_KEY] = False
    context.user_data[WAITING_LEAD_KEY] = "individual"

    await ensure_user(update, source="bot")

    await query.edit_message_text(
        "📩 *Запись на индивидуальную терапию*\n\n"
        "Отправь одним сообщением:\n"
        "1) Имя\n"
        "2) Телефон или @username\n"
        "3) Коротко запрос (по желанию)\n\n"
        "Пример: Иван, +46..., хочу меньше тревоги",
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def begin_booking_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[AI_MODE_KEY] = False
    context.user_data[WAITING_LEAD_KEY] = "group"

    await ensure_user(update, source="bot")

    await query.edit_message_text(
        "📩 *Запись в терапевтическую группу*\n\n"
        "Отправь одним сообщением:\n"
        "1) Имя\n"
        "2) Телефон или @username\n"
        "3) Коротко ожидания от группы (по желанию)\n\n"
        "Пример: Анна, @anna, хочу научиться говорить о чувствах",
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def handle_lead_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловим заявки только если активен WAITING_LEAD."""
    mode = context.user_data.get(WAITING_LEAD_KEY)
    if not mode:
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Напиши текстом, пожалуйста 🙂")
        return

    # можно гарантировать user в БД и здесь (на случай если заявка пришла без /start)
    await ensure_user(update, source="bot")

    user = update.effective_user
    lead_type = "Индивидуально" if mode == "individual" else "Группа"

    lead_payload = (
        f"🆕 Заявка: *{lead_type}*\n"
        f"👤 {user.first_name} {user.last_name or ''} (@{user.username or '—'})\n"
        f"🆔 tg_id: `{user.id}`\n\n"
        f"💬 Сообщение:\n{text}"
    )

    # Сбрасываем режим заявки
    context.user_data[WAITING_LEAD_KEY] = None

    # Отправка админу (если задано)
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=lead_payload,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.exception("Не смог отправить заявку админу: %s", e)

    await update.message.reply_text(
        "✅ Спасибо! Заявка принята. Мы скоро свяжемся.",
        reply_markup=get_main_menu(),
    )


# --------- AI ---------

async def show_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await ensure_user(update, source="bot")

    user_id = update.effective_user.id
    chat_histories[user_id] = []  # сбрасываем историю при входе

    context.user_data[WAITING_LEAD_KEY] = None
    context.user_data[AI_MODE_KEY] = True

    await query.edit_message_text(
        AI_HINT,
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    AI отвечает только в режиме AI_MODE.
    Данные о мероприятиях подтягиваются в core.ai (PostgreSQL).
    """
    # 1) если ждём заявку — AI не нужен
    if context.user_data.get(WAITING_LEAD_KEY):
        return

    # 2) если пользователь не в AI-режиме — не перехватываем текст
    if not context.user_data.get(AI_MODE_KEY):
        return

    # гарантируем user (чтобы потом сохранять историю/события/платежи на пользователя)
    await ensure_user(update, source="bot")

    user_id = update.effective_user.id
    user_message = (update.message.text or "").strip()

    if not user_message or user_message.startswith("/"):
        return

    try:
        history = chat_histories.get(user_id, [])
        response, new_history = await ai_service.chat(user_message, history)
        chat_histories[user_id] = new_history
        await update.message.reply_text(response)
    except Exception as e:
        logger.exception("AI error: %s", e)
        await update.message.reply_text("😕 Сейчас не получилось ответить. Попробуй чуть позже.")


# --------- Help ---------

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _reset_states(context)

    await ensure_user(update, source="bot")

    text = (
        "📚 *Помощь*\n\n"
        "• /start — перезапуск\n"
        "• 📅 Мероприятия — список ближайших\n"
        "• 🎓 Консультации — гештальт + запись\n"
        "• 🤖 AI — вопросы\n\n"
        "Если не получается — напиши сюда, я помогу 🙂"
    )
    await query.edit_message_text(text, reply_markup=get_back_to_menu_kb(), parse_mode="Markdown")


# ============ App ============

def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))

    # Sections
    app.add_handler(CallbackQueryHandler(show_events, pattern="^events$"))
    app.add_handler(CallbackQueryHandler(show_consultations, pattern="^consultations$"))
    app.add_handler(CallbackQueryHandler(show_formats_and_prices, pattern="^consult_formats$"))
    app.add_handler(CallbackQueryHandler(show_ai_chat, pattern="^ai_chat$"))
    app.add_handler(CallbackQueryHandler(show_help, pattern="^help$"))

    # Booking
    app.add_handler(CallbackQueryHandler(begin_booking_individual, pattern="^book_individual$"))
    app.add_handler(CallbackQueryHandler(begin_booking_group, pattern="^book_group$"))

    # Messages routing:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lead_message), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message), group=1)

    return app


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = build_app()
    logger.info("🚀 Renata Bot запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
