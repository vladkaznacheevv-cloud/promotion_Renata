import os
import logging
import re
import socket
import hashlib
import atexit
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import select, text, func
import core.models
import core.db.database as db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from core.users.service import UserService
from core.users.models import User
from core.events.service import EventService
from core.crm.service import CRMService
from core.ai.ai_service import AIService
from core.crm.activity_service import ActivityService
from core.payments.models import Payment
from core.catalog.models import CatalogItem
from telegram.error import Conflict
from telegram import Message, CallbackQuery

from telegram_bot.keyboards import (
    get_main_menu,
    get_back_to_menu_kb,
    get_consultations_menu,
    get_consultation_formats_menu,
    get_event_actions_kb,
    get_courses_nav_kb,
    get_contact_request_kb,
    get_remove_reply_kb,
    get_retry_kb,
)
from telegram_bot.text_utils import normalize_text_for_telegram, looks_like_mojibake
from telegram_bot.text_formatting import format_event_card
from telegram_bot.lock_utils import get_lock_path

try:
    import fcntl  # Linux/WSL containers
except Exception:  # pragma: no cover - linux runtime expected
    fcntl = None

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ??????? ?????? ???? ?????????
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "mistralai/devstral-2512")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ
TG_PRIVATE_CHANNEL_INVITE_LINK = os.getenv("TG_PRIVATE_CHANNEL_INVITE_LINK")

# Services
ai_service = AIService(api_key=AI_API_KEY, model=AI_MODEL)
logger.info("AI configured: key=%s model=%s", bool(AI_API_KEY), AI_MODEL)


# In-memory (РїРѕР·Р¶Рµ РјРѕР¶РЅРѕ РІС‹РЅРµСЃС‚Рё РёСЃС‚РѕСЂРёСЋ РІ Redis/DB)
chat_histories: dict[int, list[dict]] = {}

# User states
WAITING_LEAD_KEY = "waiting_lead"  # None | "individual" | "group"
AI_MODE_KEY = "ai_mode"            # bool
WAITING_CONTACT_PHONE_KEY = "waiting_contact_phone"
WAITING_CONTACT_EMAIL_KEY = "waiting_contact_email"
CONTACT_PHONE_KEY = "contact_phone"
SKIP_NEXT_EMAIL_KEY = "skip_next_email"
LOCK_FILE_PATH = get_lock_path()
_BOT_LOCK_FD = None

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
COURSES_PAGE_SIZE = 5


def _instance_meta() -> dict[str, str]:
    host = socket.gethostname()
    pid = str(os.getpid())
    token_hash = hashlib.sha256((BOT_TOKEN or "").encode("utf-8")).hexdigest()[:10]
    return {"host": host, "pid": pid, "token_hash": token_hash}


def _acquire_single_instance_lock() -> bool:
    global _BOT_LOCK_FD
    if fcntl is None:
        logger.warning("fcntl unavailable; single-instance lock is disabled")
        return True

    lock_path = LOCK_FILE_PATH
    fd = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("Bot lock busy: %s. Another bot instance is already running.", lock_path)
        fd.close()
        return False

    meta = _instance_meta()
    fd.seek(0)
    fd.truncate(0)
    fd.write(f"pid={meta['pid']} host={meta['host']} token_hash={meta['token_hash']}\n")
    fd.flush()
    _BOT_LOCK_FD = fd

    def _release() -> None:
        global _BOT_LOCK_FD
        if _BOT_LOCK_FD is None:
            return
        try:
            fcntl.flock(_BOT_LOCK_FD.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            _BOT_LOCK_FD.close()
        except Exception:
            pass
        _BOT_LOCK_FD = None

    atexit.register(_release)
    return True


def _t(text: str | None, *, label: str | None = None) -> str | None:
    return normalize_text_for_telegram(text, label=label)


async def _reply(message: Message | None, text: str | None, **kwargs):
    if message is None:
        return None
    return await message.reply_text(_t(text, label="reply") or "", **kwargs)


async def _edit(query: CallbackQuery | None, text: str | None, **kwargs):
    if query is None:
        return None
    return await query.edit_message_text(_t(text, label="edit") or "", **kwargs)


async def _send(bot, chat_id: int, text: str | None = None, **kwargs):
    payload = text if text is not None else kwargs.pop("text", None)
    return await bot.send_message(chat_id=chat_id, text=_t(payload, label="send") or "", **kwargs)


async def _answer(query: CallbackQuery, text: str | None = None, **kwargs):
    if text is None:
        return await query.answer(**kwargs)
    return await query.answer(_t(text, label="answer"), **kwargs)


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _short_text(value: str | None, limit: int = 420) -> str:
    if not value:
        return "Описание не указано."
    text = normalize_text_for_telegram(value) or value
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _format_catalog_price(price_value) -> str:
    try:
        if price_value is None:
            return "Цена по запросу"
        price = int(float(price_value))
        if price <= 0:
            return "Бесплатно"
        return f"{price} ₽"
    except Exception:
        return "Цена по запросу"


def _format_catalog_item_card(item: CatalogItem) -> str:
    title = normalize_text_for_telegram(item.title) or "Без названия"
    description = _short_text(item.description)
    price_text = _format_catalog_price(item.price)
    return (
        f"{title}\n"
        f"💳 {price_text}\n\n"
        f"{description}"
    )

GESTALT_SHORT_SCREEN_1 = (
    "рџ§  *Р“РµС€С‚Р°Р»СЊС‚-С‚РµСЂР°РїРёСЏ*\n\n"
    "РџРѕРјРѕРіР°РµС‚:\n"
    "вЂў Р»СѓС‡С€Рµ РїРѕРЅРёРјР°С‚СЊ СЃРІРѕРё С‡СѓРІСЃС‚РІР°\n"
    "вЂў СЃРЅРёР¶Р°С‚СЊ РІРЅСѓС‚СЂРµРЅРЅРµРµ РЅР°РїСЂСЏР¶РµРЅРёРµ\n"
    "вЂў Р¶РёС‚СЊ РѕСЃРѕР·РЅР°РЅРЅРѕ В«Р·РґРµСЃСЊ Рё СЃРµР№С‡Р°СЃВ»\n\n"
    "Р­С‚Рѕ РїСЂРѕ Р¶РёРІРѕР№ РєРѕРЅС‚Р°РєС‚ СЃ СЃРѕР±РѕР№ Рё Р»СЋРґСЊРјРё,\n"
    "Р° РЅРµ РїСЂРѕ СЃРѕРІРµС‚С‹ В«РєР°Рє РїСЂР°РІРёР»СЊРЅРѕВ»."
)

GESTALT_SHORT_SCREEN_2 = (
    "рџЋ“ *Р¤РѕСЂРјР°С‚С‹ Рё С†РµРЅС‹*\n\n"
    "рџ‘¤ *РЅРґРёРІРёРґСѓР°Р»СЊРЅР°СЏ С‚РµСЂР°РїРёСЏ*\n"
    "Р›РёС‡РЅРѕРµ РїСЂРѕСЃС‚СЂР°РЅСЃС‚РІРѕ РґР»СЏ СЂР°Р±РѕС‚С‹ СЃ СЃРѕР±РѕР№.\n"
    "рџ’° Р¦РµРЅР°: *СѓС‚РѕС‡РЅСЏРµС‚СЃСЏ РїСЂРё Р·Р°РїРёСЃРё*\n\n"
    "рџ‘Ґ *Р“СЂСѓРїРїРѕРІР°СЏ С‚РµСЂР°РїРёСЏ*\n"
    "Р‘РµР·РѕРїР°СЃРЅР°СЏ РіСЂСѓРїРїР° РґР»СЏ РїРѕРґРґРµСЂР¶РєРё Рё РѕРїС‹С‚Р°.\n"
    "рџ’° Р¦РµРЅР°: *СѓС‚РѕС‡РЅСЏРµС‚СЃСЏ РїСЂРё Р·Р°РїРёСЃРё*\n\n"
    "Р’ РїСЂРѕС†РµСЃСЃРµ РІС‹:\n"
    "вЂ“ Р»СѓС‡С€Рµ РїРѕРЅРёРјР°РµС‚Рµ СЃРµР±СЏ\n"
    "вЂ“ СѓС‡РёС‚РµСЃСЊ РІС‹СЃС‚СЂР°РёРІР°С‚СЊ РіСЂР°РЅРёС†С‹\n"
    "вЂ“ СЃС‚Р°РЅРѕРІРёС‚РµСЃСЊ СЃРІРѕР±РѕРґРЅРµРµ Рё С‡РµСЃС‚РЅРµРµ"
)

AI_HINT = (
    "рџ¤– *Mimo* РіРѕС‚РѕРІ РїРѕРјРѕС‡СЊ.\n\n"
    "Р—Р°РґР°Р№ РІРѕРїСЂРѕСЃ вЂ” РїСЂРѕ РјРµСЂРѕРїСЂРёСЏС‚РёСЏ, РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё РёР»Рё VIP."
)


# ============ Helpers ============

def _reset_states(context: ContextTypes.DEFAULT_TYPE):
    context.user_data[WAITING_LEAD_KEY] = None
    context.user_data[AI_MODE_KEY] = False
    context.user_data[WAITING_CONTACT_PHONE_KEY] = False
    context.user_data[WAITING_CONTACT_EMAIL_KEY] = False
    context.user_data.pop(CONTACT_PHONE_KEY, None)
    context.user_data.pop(SKIP_NEXT_EMAIL_KEY, None)


async def _notify_db_unavailable(update: Update):
    text = "вљ пёЏ РўРµС…СЂР°Р±РѕС‚С‹ СЃ Р±Р°Р·РѕР№. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ."
    keyboard = get_retry_kb()

    if update.callback_query:
        try:
            await _answer(update.callback_query)
            await _edit(update.callback_query, text, reply_markup=keyboard)
            return
        except Exception:
            logger.exception("РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РїСЂРё РѕС€РёР±РєРµ Р‘Р”")

    if update.effective_message:
        await _reply(update.effective_message, text, reply_markup=keyboard)


async def ensure_user(update: Update, source: str = "bot", ai_increment: int = 0):
    """
    Р•РґРёРЅР°СЏ С‚РѕС‡РєР°: СЃРѕР·РґР°С‘Рј/РѕР±РЅРѕРІР»СЏРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р‘Р” РїРѕ tg_id.
    Р’РѕР·РІСЂР°С‰Р°РµС‚ РѕР±СЉРµРєС‚ User (РёР· Р‘Р”).
    """
    tg_user = update.effective_user
    if tg_user is None:
        return None

    try:
        db.init_db()
        async with db.async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_or_create_by_tg_id(
                tg_id=tg_user.id,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                username=tg_user.username,
                source=source,
                update_if_exists=True,
            )
            now = datetime.utcnow()
            if not user.crm_stage:
                user.crm_stage = User.CRM_STAGE_NEW
            user.crm_stage = CRMService.stage_after_message(user.crm_stage)
            user.last_activity_at = now
            user.updated_at = now

            activity_service = ActivityService(session)
            await activity_service.upsert(
                user_id=user.id,
                last_activity_at=now,
                ai_increment=ai_increment,
            )
            await session.commit()
            return user
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ ensure_user: %s", e)
        await _notify_db_unavailable(update)
        return None


# ============ Handlers ============

async def ensure_user_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update, source="bot")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # РіР°СЂР°РЅС‚РёСЂСѓРµРј РЅР°Р»РёС‡РёРµ user РІ Р‘Р”
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    _reset_states(context)

    tg_user = update.effective_user
    name = (tg_user.first_name if tg_user else None) or (user_db.first_name if user_db else "РґСЂСѓРі")

    text = (
        f"рџЋ‰ РџСЂРёРІРµС‚, {name}!\n\n"
        "Renata Promotion вЂ” Р±РѕС‚ РїСЂРѕ РјРµСЂРѕРїСЂРёСЏС‚РёСЏ Рё С‚РµСЂР°РїРёСЋ.\n\n"
        "Р’С‹Р±РµСЂРё СЂР°Р·РґРµР» рџ‘‡"
    )
    await _reply(update.message, text, reply_markup=get_main_menu())


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)
    await _edit(query, "рџ“‹ Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ", reply_markup=get_main_menu())


async def show_contacts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    _reset_states(context)
    context.user_data[WAITING_CONTACT_PHONE_KEY] = True

    await _edit(query, 
        "РћСЃС‚Р°РІСЊС‚Рµ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° РєРЅРѕРїРєРѕР№ РЅРёР¶Рµ РёР»Рё РѕС‚РїСЂР°РІСЊС‚Рµ РЅРѕРјРµСЂ С‚РµРєСЃС‚РѕРј РІ СЌС‚РѕРј С‡Р°С‚Рµ."
    )
    await _send(context.bot, 
        chat_id=update.effective_chat.id,
        text="РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ В«РћС‚РїСЂР°РІРёС‚СЊ РЅРѕРјРµСЂВ».",
        reply_markup=get_contact_request_kb(),
    )


async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await _answer(query)

    tg_user = update.effective_user
    if tg_user is None:
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            user = await crm_service.set_client_stage_by_tg_id(
                tg_id=tg_user.id,
                stage=User.CRM_STAGE_MANAGER_FOLLOWUP,
            )
            if user is None:
                user_service = UserService(session)
                await user_service.get_or_create_by_tg_id(
                    tg_id=tg_user.id,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    username=tg_user.username,
                    source="bot",
                    update_if_exists=True,
                )
                await crm_service.set_client_stage_by_tg_id(
                    tg_id=tg_user.id,
                    stage=User.CRM_STAGE_MANAGER_FOLLOWUP,
                )
            await session.commit()

        text = "РџСЂРёРЅСЏС‚Рѕ. РњРµРЅРµРґР¶РµСЂ СЃРІСЏР¶РµС‚СЃСЏ СЃ РІР°РјРё РІ Р±Р»РёР¶Р°Р№С€РµРµ РІСЂРµРјСЏ."
        if query:
            await _edit(query, text, reply_markup=get_main_menu())
        elif update.effective_message:
            await _reply(update.effective_message, text, reply_markup=get_main_menu())
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ contact_manager: %s", e)
        await _notify_db_unavailable(update)


async def _save_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str, email: str):
    tg_user = update.effective_user
    if tg_user is None:
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            result = await crm_service.update_client_contacts(
                tg_id=tg_user.id,
                phone=phone,
                email=email,
            )
            if result is None:
                user_service = UserService(session)
                await user_service.get_or_create_by_tg_id(
                    tg_id=tg_user.id,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    username=tg_user.username,
                    source="bot",
                    update_if_exists=True,
                )
                await crm_service.update_client_contacts(
                    tg_id=tg_user.id,
                    phone=phone,
                    email=email,
                )
            await session.commit()

        _reset_states(context)
        if update.effective_message:
            await _reply(update.effective_message, 
                "РЎРїР°СЃРёР±Рѕ! РљРѕРЅС‚Р°РєС‚С‹ СЃРѕС…СЂР°РЅРµРЅС‹. РњРµРЅРµРґР¶РµСЂ СЃРІСЏР¶РµС‚СЃСЏ СЃ РІР°РјРё.",
                reply_markup=get_remove_reply_kb(),
            )
            await _reply(update.effective_message, 
                "Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ",
                reply_markup=get_main_menu(),
            )
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєРѕРЅС‚Р°РєС‚РѕРІ: %s", e)
        await _notify_db_unavailable(update)


async def handle_contact_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(WAITING_CONTACT_PHONE_KEY):
        return
    if not update.message or not update.message.contact:
        return

    contact = update.message.contact
    phone = (contact.phone_number or "").strip()
    if not phone:
        await _reply(update.message, "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РЅРѕРјРµСЂ. РћС‚РїСЂР°РІСЊС‚Рµ РЅРѕРјРµСЂ С‚РµРєСЃС‚РѕРј.")
        return

    context.user_data[CONTACT_PHONE_KEY] = phone
    context.user_data[WAITING_CONTACT_PHONE_KEY] = False
    context.user_data[WAITING_CONTACT_EMAIL_KEY] = True
    context.user_data[SKIP_NEXT_EMAIL_KEY] = True
    await _reply(update.message, "РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ email С‚РµРєСЃС‚РѕРј.", reply_markup=get_remove_reply_kb())


async def handle_contact_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(WAITING_CONTACT_PHONE_KEY):
        return
    if not update.message or not update.message.text:
        return

    text = (update.message.text or "").strip()
    if text.lower() == "РѕС‚РјРµРЅР°":
        _reset_states(context)
        await _reply(update.message, "Р”РµР№СЃС‚РІРёРµ РѕС‚РјРµРЅРµРЅРѕ.", reply_markup=get_main_menu())
        return

    normalized = re.sub(r"[^\\d+]", "", text)
    if len(re.sub(r"\\D", "", normalized)) < 10:
        await _reply(update.message, "РќРѕРјРµСЂ РІС‹РіР»СЏРґРёС‚ РЅРµРєРѕСЂСЂРµРєС‚РЅРѕ. РџСЂРёРјРµСЂ: +79991234567")
        return

    context.user_data[CONTACT_PHONE_KEY] = normalized
    context.user_data[WAITING_CONTACT_PHONE_KEY] = False
    context.user_data[WAITING_CONTACT_EMAIL_KEY] = True
    context.user_data[SKIP_NEXT_EMAIL_KEY] = True
    await _reply(update.message, "РћС‚Р»РёС‡РЅРѕ. РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ email С‚РµРєСЃС‚РѕРј.", reply_markup=get_remove_reply_kb())


async def handle_contact_email_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop(SKIP_NEXT_EMAIL_KEY, False):
        return
    if not context.user_data.get(WAITING_CONTACT_EMAIL_KEY):
        return
    if not update.message or not update.message.text:
        return

    email = (update.message.text or "").strip().lower()
    if email == "РѕС‚РјРµРЅР°":
        _reset_states(context)
        await _reply(update.message, "Р”РµР№СЃС‚РІРёРµ РѕС‚РјРµРЅРµРЅРѕ.", reply_markup=get_main_menu())
        return

    if not EMAIL_RE.match(email):
        await _reply(update.message, "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ email. РџСЂРёРјРµСЂ: name@example.com")
        return

    phone = context.user_data.get(CONTACT_PHONE_KEY)
    if not phone:
        context.user_data[WAITING_CONTACT_EMAIL_KEY] = False
        context.user_data[WAITING_CONTACT_PHONE_KEY] = True
        await _reply(update.message, "РЎРЅР°С‡Р°Р»Р° РѕС‚РїСЂР°РІСЊС‚Рµ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР°.")
        return

    await _save_contacts(update, context, phone=phone, email=email)


# --------- Events ---------

async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _send_events_list(update, user_db, context, from_callback=True)


async def show_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_states(context)
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return
    await _send_events_list(update, user_db, context, from_callback=False)


async def show_courses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _send_courses_list(update, context, offset=0, from_callback=True)


async def show_courses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_states(context)
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return
    await _send_courses_list(update, context, offset=0, from_callback=False)


async def show_courses_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    try:
        offset = int((query.data or "").split(":")[1])
    except Exception:
        offset = 0

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _send_courses_list(update, context, offset=max(offset, 0), from_callback=True)


# --------- Consultations / Gestalt ---------

async def show_consultations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _edit(query, 
        GESTALT_SHORT_SCREEN_1,
        parse_mode="Markdown",
        reply_markup=get_consultations_menu(),
    )


async def show_formats_and_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _edit(query, 
        GESTALT_SHORT_SCREEN_2,
        parse_mode="Markdown",
        reply_markup=get_consultation_formats_menu(),
    )


async def begin_booking_individual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    context.user_data[AI_MODE_KEY] = False
    context.user_data[WAITING_LEAD_KEY] = "individual"

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _edit(query, 
        "рџ“© *Р—Р°РїРёСЃСЊ РЅР° РёРЅРґРёРІРёРґСѓР°Р»СЊРЅСѓСЋ С‚РµСЂР°РїРёСЋ*\n\n"
        "РћС‚РїСЂР°РІСЊ РѕРґРЅРёРј СЃРѕРѕР±С‰РµРЅРёРµРј:\n"
        "1) РјСЏ\n"
        "2) РўРµР»РµС„РѕРЅ РёР»Рё @username\n"
        "3) РљРѕСЂРѕС‚РєРѕ Р·Р°РїСЂРѕСЃ (РїРѕ Р¶РµР»Р°РЅРёСЋ)\n\n"
        "РџСЂРёРјРµСЂ: РІР°РЅ, +46..., С…РѕС‡Сѓ РјРµРЅСЊС€Рµ С‚СЂРµРІРѕРіРё",
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def begin_booking_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    context.user_data[AI_MODE_KEY] = False
    context.user_data[WAITING_LEAD_KEY] = "group"

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    await _edit(query, 
        "рџ“© *Р—Р°РїРёСЃСЊ РІ С‚РµСЂР°РїРµРІС‚РёС‡РµСЃРєСѓСЋ РіСЂСѓРїРїСѓ*\n\n"
        "РћС‚РїСЂР°РІСЊ РѕРґРЅРёРј СЃРѕРѕР±С‰РµРЅРёРµРј:\n"
        "1) РјСЏ\n"
        "2) РўРµР»РµС„РѕРЅ РёР»Рё @username\n"
        "3) РљРѕСЂРѕС‚РєРѕ РѕР¶РёРґР°РЅРёСЏ РѕС‚ РіСЂСѓРїРїС‹ (РїРѕ Р¶РµР»Р°РЅРёСЋ)\n\n"
        "РџСЂРёРјРµСЂ: РђРЅРЅР°, @anna, С…РѕС‡Сѓ РЅР°СѓС‡РёС‚СЊСЃСЏ РіРѕРІРѕСЂРёС‚СЊ Рѕ С‡СѓРІСЃС‚РІР°С…",
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def handle_lead_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Р›РѕРІРёРј Р·Р°СЏРІРєРё С‚РѕР»СЊРєРѕ РµСЃР»Рё Р°РєС‚РёРІРµРЅ WAITING_LEAD."""
    if context.user_data.get(WAITING_CONTACT_PHONE_KEY) or context.user_data.get(WAITING_CONTACT_EMAIL_KEY):
        return

    mode = context.user_data.get(WAITING_LEAD_KEY)
    if not mode:
        return

    text = (update.message.text or "").strip()
    if not text:
        await _reply(update.message, "РќР°РїРёС€Рё С‚РµРєСЃС‚РѕРј, РїРѕР¶Р°Р»СѓР№СЃС‚Р° рџ™‚")
        return

    # РјРѕР¶РЅРѕ РіР°СЂР°РЅС‚РёСЂРѕРІР°С‚СЊ user РІ Р‘Р” Рё Р·РґРµСЃСЊ (РЅР° СЃР»СѓС‡Р°Р№ РµСЃР»Рё Р·Р°СЏРІРєР° РїСЂРёС€Р»Р° Р±РµР· /start)
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    user = update.effective_user
    lead_type = "РЅРґРёРІРёРґСѓР°Р»СЊРЅРѕ" if mode == "individual" else "Р“СЂСѓРїРїР°"

    lead_payload = (
        f"рџ†• Р—Р°СЏРІРєР°: *{lead_type}*\n"
        f"рџ‘¤ {user.first_name} {user.last_name or ''} (@{user.username or 'вЂ”'})\n"
        f"рџ†” tg_id: `{user.id}`\n\n"
        f"рџ’¬ РЎРѕРѕР±С‰РµРЅРёРµ:\n{text}"
    )

    # РЎР±СЂР°СЃС‹РІР°РµРј СЂРµР¶РёРј Р·Р°СЏРІРєРё
    context.user_data[WAITING_LEAD_KEY] = None

    # РћС‚РїСЂР°РІРєР° Р°РґРјРёРЅСѓ (РµСЃР»Рё Р·Р°РґР°РЅРѕ)
    if ADMIN_CHAT_ID:
        try:
            await _send(context.bot, 
                chat_id=int(ADMIN_CHAT_ID),
                text=lead_payload,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.exception("РќРµ СЃРјРѕРі РѕС‚РїСЂР°РІРёС‚СЊ Р·Р°СЏРІРєСѓ Р°РґРјРёРЅСѓ: %s", e)

    await _reply(update.message, 
        "вњ… РЎРїР°СЃРёР±Рѕ! Р—Р°СЏРІРєР° РїСЂРёРЅСЏС‚Р°. РњС‹ СЃРєРѕСЂРѕ СЃРІСЏР¶РµРјСЃСЏ.",
        reply_markup=get_main_menu(),
    )


# --------- AI ---------

async def show_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    user_id = update.effective_user.id
    chat_histories[user_id] = []  # СЃР±СЂР°СЃС‹РІР°РµРј РёСЃС‚РѕСЂРёСЋ РїСЂРё РІС…РѕРґРµ

    context.user_data[WAITING_LEAD_KEY] = None
    context.user_data[AI_MODE_KEY] = True

    await _edit(query, 
        AI_HINT,
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_kb(),
    )


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    AI РѕС‚РІРµС‡Р°РµС‚ С‚РѕР»СЊРєРѕ РІ СЂРµР¶РёРјРµ AI_MODE.
    Р”Р°РЅРЅС‹Рµ Рѕ РјРµСЂРѕРїСЂРёСЏС‚РёСЏС… РїРѕРґС‚СЏРіРёРІР°СЋС‚СЃСЏ РІ core.ai (PostgreSQL).
    """
    # 1) РµСЃР»Рё Р¶РґС‘Рј Р·Р°СЏРІРєСѓ вЂ” AI РЅРµ РЅСѓР¶РµРЅ
    if context.user_data.get(WAITING_LEAD_KEY):
        return
    if context.user_data.get(WAITING_CONTACT_PHONE_KEY) or context.user_data.get(WAITING_CONTACT_EMAIL_KEY):
        return

    # 2) РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РІ AI-СЂРµР¶РёРјРµ вЂ” РЅРµ РїРµСЂРµС…РІР°С‚С‹РІР°РµРј С‚РµРєСЃС‚
    if not context.user_data.get(AI_MODE_KEY):
        return

    # РіР°СЂР°РЅС‚РёСЂСѓРµРј user (С‡С‚РѕР±С‹ РїРѕС‚РѕРј СЃРѕС…СЂР°РЅСЏС‚СЊ РёСЃС‚РѕСЂРёСЋ/СЃРѕР±С‹С‚РёСЏ/РїР»Р°С‚РµР¶Рё РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ)
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    user_id = update.effective_user.id
    user_message = (update.message.text or "").strip()

    if not user_message or user_message.startswith("/"):
        return

    try:
        history = chat_histories.get(user_id, [])
        response, new_history = await ai_service.chat(user_message, history)
        chat_histories[user_id] = new_history
        if user_db is not None:
            async with db.async_session() as session:
                activity_service = ActivityService(session)
                await activity_service.upsert(
                    user_id=user_db.id,
                    last_activity_at=datetime.utcnow(),
                    ai_increment=1,
                )
                await session.commit()
        await _reply(update.message, response)
    except Exception as e:
        logger.exception("AI error: %s", e)
        await _reply(update.message, " РЎРµР№С‡Р°СЃ РЅРµ РїРѕР»СѓС‡РёР»РѕСЃСЊ РѕС‚РІРµС‚РёС‚СЊ. РџРѕРїСЂРѕР±СѓР№ С‡СѓС‚СЊ РїРѕР·Р¶Рµ.")


# --------- Help ---------

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)
    _reset_states(context)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    text = (
        "рџ“љ *РџРѕРјРѕС‰СЊ*\n\n"
        "вЂў /start вЂ” РїРµСЂРµР·Р°РїСѓСЃРє\n"
        "вЂў рџ“… РњРµСЂРѕРїСЂРёСЏС‚РёСЏ вЂ” СЃРїРёСЃРѕРє Р±Р»РёР¶Р°Р№С€РёС…\n"
        "вЂў рџЋ“ РљРѕРЅСЃСѓР»СЊС‚Р°С†РёРё вЂ” РіРµС€С‚Р°Р»СЊС‚ + Р·Р°РїРёСЃСЊ\n"
        "вЂў рџ¤– AI вЂ” РІРѕРїСЂРѕСЃС‹\n\n"
        "Р•СЃР»Рё РЅРµ РїРѕР»СѓС‡Р°РµС‚СЃСЏ вЂ” РЅР°РїРёС€Рё СЃСЋРґР°, СЏ РїРѕРјРѕРіСѓ рџ™‚"
    )
    await _edit(query, text, reply_markup=get_back_to_menu_kb(), parse_mode="Markdown")


# --------- Errors / Retry ---------

async def retry_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    if query:
        await _edit(query, "вњ… Р‘Р°Р·Р° СЃРЅРѕРІР° РґРѕСЃС‚СѓРїРЅР°.", reply_markup=get_main_menu())
    elif update.effective_message:
        await _reply(update.effective_message, "вњ… Р‘Р°Р·Р° СЃРЅРѕРІР° РґРѕСЃС‚СѓРїРЅР°.", reply_markup=get_main_menu())


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error: %s", context.error)
    if isinstance(update, Update):
        await _notify_db_unavailable(update)


async def _send_events_list(
    update: Update,
    user_db,
    context: ContextTypes.DEFAULT_TYPE,
    from_callback: bool,
):
    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            events_result = await crm_service.list_active_events()
            events = events_result.get("items", [])
            if not events:
                message = "рџ“… РЎРєРѕСЂРѕ РїРѕСЏРІСЏС‚СЃСЏ РЅРѕРІС‹Рµ РјРµСЂРѕРїСЂРёСЏС‚РёСЏ!"
                if from_callback and update.callback_query:
                    await _edit(update.callback_query, 
                        message, reply_markup=get_back_to_menu_kb()
                    )
                elif update.effective_message:
                    await _reply(update.effective_message, 
                        message, reply_markup=get_back_to_menu_kb()
                    )
                return

            event_service = EventService(session)

            header = "рџ“… *Р‘Р»РёР¶Р°Р№С€РёРµ РјРµСЂРѕРїСЂРёСЏС‚РёСЏ*\nР’С‹Р±РµСЂРёС‚Рµ СЃРѕР±С‹С‚РёРµ Рё Р·Р°РїРёС€РёС‚РµСЃСЊ:"
            if from_callback and update.callback_query:
                await _edit(update.callback_query, 
                    header, parse_mode="Markdown", reply_markup=get_back_to_menu_kb()
                )
            elif update.effective_message:
                await _reply(update.effective_message, 
                    header, parse_mode="Markdown", reply_markup=get_back_to_menu_kb()
                )

            for event in events:
                event_id = event["id"]
                registered = await event_service.is_user_registered(user_db.id, event_id)
                for field_name in ("title", "description", "location"):
                    raw = event.get(field_name)
                    if isinstance(raw, str) and looks_like_mojibake(raw):
                        logger.warning(
                            "Detected mojibake in event.%s id=%s repr=%r utf8_len=%s",
                            field_name,
                            event_id,
                            raw,
                            len(raw.encode("utf-8", errors="replace")),
                        )

                text = format_event_card(event)
                gc_link = event.get("link_getcourse")
                await _send(context.bot, 
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=get_event_actions_kb(
                        event_id,
                        registered,
                        gc_link if _is_valid_http_url(gc_link) else None,
                    ),
                )
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ show_events: %s", e)
        await _notify_db_unavailable(update)


async def _send_courses_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    offset: int = 0,
    from_callback: bool,
):
    try:
        db.init_db()
        async with db.async_session() as session:
            total = await session.scalar(
                select(func.count(CatalogItem.id))
                .where(CatalogItem.status == "active")
                .where(CatalogItem.link_getcourse.is_not(None))
            )
            rows = await session.execute(
                select(CatalogItem)
                .where(CatalogItem.status == "active")
                .where(CatalogItem.link_getcourse.is_not(None))
                .order_by(CatalogItem.updated_at.desc().nulls_last(), CatalogItem.id.desc())
                .limit(COURSES_PAGE_SIZE)
                .offset(offset)
            )
            items = rows.scalars().all()

            total_value = int(total or 0)
            if not items:
                message = "Онлайн-курсы пока недоступны. Попробуйте позже."
                if from_callback and update.callback_query:
                    await _edit(update.callback_query, message, reply_markup=get_back_to_menu_kb())
                elif update.effective_message:
                    await _reply(update.effective_message, message, reply_markup=get_back_to_menu_kb())
                return

            page_from = offset + 1
            page_to = min(offset + len(items), total_value)
            header = f"Онлайн-курсы: {page_from}-{page_to} из {total_value}"
            nav_markup = get_courses_nav_kb(offset=offset, limit=COURSES_PAGE_SIZE, total=total_value)

            if from_callback and update.callback_query:
                await _edit(update.callback_query, header, reply_markup=nav_markup)
            elif update.effective_message:
                await _reply(update.effective_message, header, reply_markup=nav_markup)

            for item in items:
                link = item.link_getcourse if _is_valid_http_url(item.link_getcourse) else None
                markup = (
                    InlineKeyboardMarkup([[InlineKeyboardButton("Перейти на GetCourse", url=link)]])
                    if link
                    else get_back_to_menu_kb()
                )
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=_format_catalog_item_card(item),
                    reply_markup=markup,
                )
    except Exception as e:
        logger.exception("Ошибка БД в show_courses: %s", e)
        await _notify_db_unavailable(update)


async def event_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    try:
        event_id = int(query.data.split(":")[1])
    except Exception:
        await _answer(query, "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id", show_alert=True)
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            tg_id = update.effective_user.id if update.effective_user else user_db.tg_id
            result = await crm_service.add_attendee_by_tg_id(event_id, tg_id)
            if not result.get("ok") and result.get("error") == "event_not_found":
                await _answer(query, "РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ", show_alert=True)
                return
            if not result.get("ok") and result.get("error") == "user_not_found":
                await _answer(query, "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ", show_alert=True)
                return
            await session.commit()
            await query.edit_message_reply_markup(
                reply_markup=get_event_actions_kb(event_id, registered=True)
            )
            await _answer(query, "Р’С‹ Р·Р°РїРёСЃР°РЅС‹!" if not result.get("already") else "Р’С‹ СѓР¶Рµ Р±С‹Р»Рё Р·Р°РїРёСЃР°РЅС‹")
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ event_register: %s", e)
        await _notify_db_unavailable(update)


async def event_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    try:
        event_id = int(query.data.split(":")[1])
    except Exception:
        await _answer(query, "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id", show_alert=True)
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            tg_id = update.effective_user.id if update.effective_user else user_db.tg_id
            result = await crm_service.remove_attendee_by_tg_id(event_id, tg_id)
            if not result.get("ok") and result.get("error") == "event_not_found":
                await _answer(query, "РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ", show_alert=True)
                return
            if not result.get("ok") and result.get("error") == "user_not_found":
                await _answer(query, "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ", show_alert=True)
                return
            await session.commit()
            await query.edit_message_reply_markup(
                reply_markup=get_event_actions_kb(event_id, registered=False)
            )
            await _answer(query, "Р—Р°РїРёСЃСЊ РѕС‚РјРµРЅРµРЅР°" if result.get("removed") else "Р’С‹ РЅРµ Р±С‹Р»Рё Р·Р°РїРёСЃР°РЅС‹")
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ event_cancel: %s", e)
        await _notify_db_unavailable(update)


async def event_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _answer(query)

    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return

    try:
        event_id = int(query.data.split(":")[1])
    except Exception:
        await _answer(query, "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id", show_alert=True)
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            event_service = EventService(session)
            event = await event_service.get_by_id(event_id)
            if not event:
                await _answer(query, "РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ", show_alert=True)
                return

            price_value = event.price
            amount = int(price_value) if price_value is not None else 0
            if amount <= 0:
                await _answer(query, "РћРїР»Р°С‚Р° РґР»СЏ СЌС‚РѕРіРѕ СЃРѕР±С‹С‚РёСЏ РїРѕРєР° РЅРµРґРѕСЃС‚СѓРїРЅР°", show_alert=True)
                return

            crm_service = CRMService(session)
            result = await crm_service.create_payment_for_user(
                tg_id=update.effective_user.id if update.effective_user else user_db.tg_id,
                event_id=event_id,
                amount=amount,
                source="yookassa",
            )
            if result is None:
                await _answer(query, "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ РїР»Р°С‚С‘Р¶", show_alert=True)
                return

            await session.commit()

            payment_link = f"https://pay.example.local/yookassa?payment_id={result['id']}"
            event_link_part = (
                f"\nСтраница мероприятия на GetCourse: {event.link_getcourse}"
                if _is_valid_http_url(event.link_getcourse)
                else ""
            )
            invite_part = (
                f"\nРџРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕРїР»Р°С‚С‹ РІС‹ РїРѕР»СѓС‡РёС‚Рµ РґРѕСЃС‚СѓРї РІ РєР°РЅР°Р»: {TG_PRIVATE_CHANNEL_INVITE_LINK}"
                if TG_PRIVATE_CHANNEL_INVITE_LINK
                else "\nРџРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕРїР»Р°С‚С‹ РјРµРЅРµРґР¶РµСЂ РѕС‚РїСЂР°РІРёС‚ СЃСЃС‹Р»РєСѓ РІ Р·Р°РєСЂС‹С‚С‹Р№ РєР°РЅР°Р»."
            )
            await _send(context.bot, 
                chat_id=update.effective_chat.id,
                text=(
                    "РџР»Р°С‚РµР¶ СЃРѕР·РґР°РЅ (pending).\n"
                    f"РЎСЃС‹Р»РєР° РґР»СЏ РѕРїР»Р°С‚С‹: {payment_link}\n"
                    "Р•СЃР»Рё РЅСѓР¶РµРЅ Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ СЃРїРѕСЃРѕР±, РЅР°Р¶РјРёС‚Рµ В«РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РјРµРЅРµРґР¶РµСЂРѕРјВ»."
                    f"{event_link_part}"
                    f"{invite_part}"
                ),
            )
    except Exception as e:
        logger.exception("РћС€РёР±РєР° Р‘Р” РІ event_pay: %s", e)
        await _notify_db_unavailable(update)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_db = await ensure_user(update, source="bot")
    if user_db is None:
        return
    _reset_states(context)
    if update.effective_message:
        await _reply(update.effective_message, "Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ", reply_markup=get_main_menu())


async def mark_paid_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    if not ADMIN_CHAT_ID or str(user.id) != str(ADMIN_CHAT_ID):
        await _reply(message, "РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ Р±РѕС‚Р°.")
        return

    args = context.args or []
    if len(args) != 2:
        await _reply(message, "Р¤РѕСЂРјР°С‚: /mark_paid <tg_id> <event_id>")
        return

    try:
        tg_id = int(args[0])
        event_id = int(args[1])
    except ValueError:
        await _reply(message, "tg_id Рё event_id РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ С‡РёСЃР»Р°РјРё.")
        return

    try:
        db.init_db()
        async with db.async_session() as session:
            crm_service = CRMService(session)
            target_user = await crm_service._get_user_by_tg_id(tg_id)
            if target_user is None:
                await _reply(message, "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
                return

            has_event_id = await crm_service._payments_has_event_id()
            payment_id: int | None = None
            if has_event_id:
                row = await session.execute(
                    select(Payment)
                    .where(Payment.user_id == target_user.id)
                    .where(Payment.event_id == event_id)
                    .order_by(Payment.created_at.desc())
                )
                payment = row.scalars().first()
                if payment is not None:
                    payment_id = payment.id
            else:
                row = await session.execute(
                    text(
                        """
                        SELECT id
                        FROM payments
                        WHERE user_id = :user_id
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"user_id": target_user.id},
                )
                row_map = row.mappings().first()
                if row_map is not None:
                    payment_id = int(row_map["id"])

            if payment_id is None:
                await _reply(message, "РџР»Р°С‚РµР¶ РЅРµ РЅР°Р№РґРµРЅ.")
                return

            await crm_service.mark_payment_status(payment_id, "paid")
            await session.commit()

        await _reply(message, 
            f"РџР»Р°С‚РµР¶ #{payment_id} РѕС‚РјРµС‡РµРЅ РєР°Рє paid РґР»СЏ tg_id={tg_id}, event_id={event_id}."
        )
        if TG_PRIVATE_CHANNEL_INVITE_LINK:
            await _send(context.bot, 
                chat_id=tg_id,
                text=(
                    "РћРїР»Р°С‚Р° РїРѕРґС‚РІРµСЂР¶РґРµРЅР°. Р’РѕС‚ СЃСЃС‹Р»РєР° РІ Р·Р°РєСЂС‹С‚С‹Р№ РєР°РЅР°Р»:\n"
                    f"{TG_PRIVATE_CHANNEL_INVITE_LINK}"
                ),
            )
    except Exception as e:
        logger.exception("РћС€РёР±РєР° РІ /mark_paid: %s", e)
        await _reply(message, "РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РјРµС‚РёС‚СЊ РѕРїР»Р°С‚Сѓ. РџСЂРѕРІРµСЂСЊС‚Рµ Р»РѕРіРё.")


# ============ App ============

def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("events", show_events_command))
    app.add_handler(CommandHandler("courses", show_courses_command))
    app.add_handler(CommandHandler("catalog", show_courses_command))
    app.add_handler(CommandHandler("mark_paid", mark_paid_dev))

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(retry_db, pattern="^retry_db$"))

    # Sections
    app.add_handler(CallbackQueryHandler(show_events, pattern="^events$"))
    app.add_handler(CallbackQueryHandler(show_courses, pattern="^courses$"))
    app.add_handler(CallbackQueryHandler(show_courses_page, pattern="^courses_page:"))
    app.add_handler(CallbackQueryHandler(show_consultations, pattern="^consultations$"))
    app.add_handler(CallbackQueryHandler(show_formats_and_prices, pattern="^consult_formats$"))
    app.add_handler(CallbackQueryHandler(show_ai_chat, pattern="^ai_chat$"))
    app.add_handler(CallbackQueryHandler(show_contacts_request, pattern="^share_contacts$"))
    app.add_handler(CallbackQueryHandler(contact_manager, pattern="^contact_manager$"))
    app.add_handler(CallbackQueryHandler(show_help, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(event_register, pattern="^event_register:"))
    app.add_handler(CallbackQueryHandler(event_cancel, pattern="^event_cancel:"))
    app.add_handler(CallbackQueryHandler(event_pay, pattern="^event_pay:"))

    # Booking
    app.add_handler(CallbackQueryHandler(begin_booking_individual, pattern="^book_individual$"))
    app.add_handler(CallbackQueryHandler(begin_booking_group, pattern="^book_group$"))

    # Messages routing:
    app.add_handler(MessageHandler(filters.ALL, ensure_user_on_message), group=-1)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact_phone), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_phone_text), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_email_text), group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lead_message), group=3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message), group=4)

    app.add_error_handler(on_error)

    return app


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not _acquire_single_instance_lock():
        logger.error("Second bot instance detected. Exiting to avoid Telegram getUpdates conflict.")
        return

    meta = _instance_meta()
    logger.info(
        "Bot instance metadata: host=%s pid=%s token_hash=%s lock=%s",
        meta["host"],
        meta["pid"],
        meta["token_hash"],
        LOCK_FILE_PATH,
    )

    app = build_app()
    logger.info("Renata Bot запущен. PID=%s", os.getpid())
    logger.warning("Polling mode: запускайте только один экземпляр бота, иначе будет Telegram Conflict.")
    try:
        db.init_db()
    except Exception as e:
        logger.exception("DB init failed, bot will run without DB: %s", e)
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Conflict:
        logger.exception(
            "Telegram polling conflict (another getUpdates consumer). host=%s pid=%s token_hash=%s",
            meta["host"],
            meta["pid"],
            meta["token_hash"],
        )
        return


if __name__ == "__main__":
    main()

