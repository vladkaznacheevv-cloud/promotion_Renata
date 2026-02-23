import os 
import json
import asyncio
import logging 
import re 
import socket 
import hashlib 
import atexit 
import threading 
from datetime import datetime
import httpx 
from dotenv import load_dotenv 
from sqlalchemy import select ,text ,func 
import core .models 
import core .db .database as db 
from telegram import Update ,InlineKeyboardButton ,InlineKeyboardMarkup 
from telegram .ext import (
Application ,
CommandHandler ,
CallbackQueryHandler ,
MessageHandler ,
ContextTypes ,
filters ,
)
from core .users .service import UserService 
from core .users .models import User 
from core .events .service import EventService 
from core .crm .service import CRMService 
from core .ai .ai_service import AIService 
from core .crm .activity_service import ActivityService 
from core .payments .models import Payment 
from core .catalog .models import CatalogItem 
from core .integrations .getcourse .url_utils import normalize_getcourse_url 
from telegram .error import Conflict ,BadRequest
from telegram import Message ,CallbackQuery 

from telegram_bot .keyboards import (
get_main_menu ,
get_back_to_menu_kb ,
get_consultations_menu ,
get_consultation_formats_menu ,
get_event_actions_kb ,
get_courses_nav_kb ,
get_courses_empty_kb ,
get_contact_manager_kb ,
get_contact_request_kb ,
get_remove_reply_kb ,
get_retry_kb ,
get_private_channel_pending_kb ,
get_private_channel_paid_kb ,
get_game10_kb ,
)
from telegram_bot .text_utils import normalize_text_for_telegram ,looks_like_mojibake 
from telegram_bot .text_formatting import format_event_card 
from telegram_bot .lock_utils import get_lock_path ,touch_lock_heartbeat 
from telegram_bot .typing_indicator import TypingIndicator 
from telegram_bot .screen_manager import ScreenManager
from telegram_bot .utils import detect_intent

try :
    import fcntl # Linux/WSL containers
except Exception :# pragma: no cover - linux runtime expected
    fcntl =None 

load_dotenv ()
logging .basicConfig (level =logging .INFO )
logger =logging .getLogger (__name__ )

# РЎРЅРёР¶Р°РµРј СѓСЂРѕРІРµРЅСЊ С€СѓРјР° РІ Р»РѕРіР°С…
logging .getLogger ("httpx").setLevel (logging .WARNING )
logging .getLogger ("telegram").setLevel (logging .WARNING )
logging .getLogger ("telegram.ext").setLevel (logging .WARNING )

BOT_TOKEN =os .getenv ("BOT_TOKEN")
AI_API_KEY =os .getenv ("OPENROUTER_API_KEY")or os .getenv ("AI_API_KEY")
ADMIN_CHAT_ID =os .getenv ("ADMIN_CHAT_ID")# опционально
TG_PRIVATE_CHANNEL_INVITE_LINK =os .getenv ("TG_PRIVATE_CHANNEL_INVITE_LINK")
CRM_API_BASE_URL =(os .getenv ("CRM_API_BASE_URL")or "http://web:8000").rstrip ("/")
CRM_API_TOKEN =(os .getenv ("CRM_API_TOKEN")or "").strip ()
YOOMONEY_PAY_URL_PLACEHOLDER =(os .getenv ("YOOMONEY_PAY_URL_PLACEHOLDER")or "").strip ()

# Services
ai_service =AIService (api_key =AI_API_KEY )
logger .info ("AI configured: key=%s model=%s",bool (AI_API_KEY ),ai_service .model )
screen_manager =ScreenManager ()


# In-memory (РїРѕР·Р¶Рµ РјРѕР¶РЅРѕ РІС‹РЅРµСЃС‚Рё РёСЃС‚РѕСЂРёСЋ РІ Redis/DB)
chat_histories :dict [int ,list [dict ]]={}

# User states
WAITING_LEAD_KEY ="waiting_lead"# None | "individual" | "group"
AI_MODE_KEY ="assistant_mode"# bool
ASSISTANT_SOURCE_KEY ="assistant_source"# None | "course"
ASSISTANT_EVENT_ID_KEY ="assistant_event_id"
WAITING_CONTACT_PHONE_KEY ="waiting_contact_phone"
WAITING_CONTACT_EMAIL_KEY ="waiting_contact_email"
CONTACT_PHONE_KEY ="contact_phone"
CONTACT_FLOW_KEY ="contact_flow"
PENDING_CONTACTS_KEY ="pending_contacts"
SKIP_NEXT_EMAIL_KEY ="skip_next_email"
LOCK_FILE_PATH =get_lock_path ()
_BOT_LOCK_FD =None 
LOCK_HEARTBEAT_SECONDS =30 

EMAIL_RE =re .compile (r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
COURSES_PAGE_SIZE =5 
EVENTS_LIST_PAGE_SIZE =6
EVENTS_CACHE_KEY ="events_cache"
EVENTS_LIST_PAGE_KEY ="events_list_page"
SCREEN_KIND_KEY ="screen_kind"
SCREEN_EVENT_ID_KEY ="screen_event_id"


def _instance_meta ()->dict [str ,str ]:
    host =socket .gethostname ()
    pid =str (os .getpid ())
    token_hash =hashlib .sha256 ((BOT_TOKEN or "").encode ("utf-8")).hexdigest ()[:10 ]
    return {"host":host ,"pid":pid ,"token_hash":token_hash }


def _acquire_single_instance_lock ()->bool :
    global _BOT_LOCK_FD 
    if fcntl is None :
        logger .warning ("fcntl unavailable; single-instance lock is disabled")
        return True 

    lock_path =LOCK_FILE_PATH 
    fd =open (lock_path ,"a+",encoding ="utf-8")
    try :
        fcntl .flock (fd .fileno (),fcntl .LOCK_EX |fcntl .LOCK_NB )
    except BlockingIOError :
        logger .error ("Bot lock busy: %s. Another bot instance is already running.",lock_path )
        fd .close ()
        return False 

    meta =_instance_meta ()
    fd .seek (0 )
    fd .truncate (0 )
    fd .write (f"pid={meta ['pid']} host={meta ['host']} token_hash={meta ['token_hash']}\n")
    fd .flush ()
    _BOT_LOCK_FD =fd 

    def _release ()->None :
        global _BOT_LOCK_FD 
        if _BOT_LOCK_FD is None :
            return 
        try :
            fcntl .flock (_BOT_LOCK_FD .fileno (),fcntl .LOCK_UN )
        except Exception :
            pass 
        try :
            _BOT_LOCK_FD .close ()
        except Exception :
            pass 
        _BOT_LOCK_FD =None 

    atexit .register (_release )
    return True 


def _start_lock_heartbeat (lock_path :str )->threading .Event :
    stop_event =threading .Event ()
    logger .info ("Lock heartbeat started: path=%s interval=%ss",lock_path ,LOCK_HEARTBEAT_SECONDS )

    def _worker ()->None :
        while not stop_event .wait (LOCK_HEARTBEAT_SECONDS ):
            if not touch_lock_heartbeat (lock_path ):
                logger .warning ("Lock heartbeat touch failed: path=%s",lock_path )

    if not touch_lock_heartbeat (lock_path ):
        logger .warning ("Initial lock heartbeat touch failed: path=%s",lock_path )
    thread =threading .Thread (target =_worker ,name ="bot-lock-heartbeat",daemon =True )
    thread .start ()
    return stop_event 


def _t (text :str |None ,*,label :str |None =None )->str |None :
    return normalize_text_for_telegram (text ,label =label )


async def _reply (message :Message |None ,text :str |None ,**kwargs ):
    if message is None :
        return None 
    return await message .reply_text (_t (text ,label ="reply")or "",**kwargs )


async def _edit (query :CallbackQuery |None ,text :str |None ,**kwargs ):
    if query is None :
        return None 
    return await query .edit_message_text (_t (text ,label ="edit")or "",**kwargs )


async def _send (bot ,chat_id :int ,text :str |None =None ,**kwargs ):
    payload =text if text is not None else kwargs .pop ("text",None )
    return await bot .send_message (chat_id =chat_id ,text =_t (payload ,label ="send")or "",**kwargs )


async def _show_screen (update :Update ,context :ContextTypes .DEFAULT_TYPE ,text :str |None ,**kwargs ):
    return await screen_manager .show_screen (update ,context ,text ,**kwargs )


async def _safe_edit_reply_markup (query :CallbackQuery |None ,*,reply_markup =None ):
    if query is None :
        return None
    try :
        return await query .edit_message_reply_markup (reply_markup =reply_markup )
    except BadRequest as e :
        message =(str (e )or "").lower ()
        if "message is not modified" in message :
            return None
        raise


async def _answer (query :CallbackQuery ,text :str |None =None ,**kwargs ):
    if text is None :
        return await query .answer (**kwargs )
    return await query .answer (_t (text ,label ="answer"),**kwargs )


def _is_valid_http_url (value :str |None )->bool :
    normalized ,_ =normalize_getcourse_url (value ,base_url =os .getenv ("GETCOURSE_BASE_URL"))
    return bool (normalized )


def _is_absolute_url (value :str |None )->bool :
    if not value :
        return False 
    normalized =str (value ).strip ()
    return normalized .startswith ("http://")or normalized .startswith ("https://")


def _private_channel_payment_url ()->str |None :
    if _is_absolute_url (YOOMONEY_PAY_URL_PLACEHOLDER ):
        return YOOMONEY_PAY_URL_PLACEHOLDER 
    return None 


async def _fetch_private_channel_from_backend (user_key :int )->dict |None :
    if not CRM_API_BASE_URL or not CRM_API_TOKEN :
        return None 
    try :
        async with httpx .AsyncClient (timeout =10.0 )as client :
            response =await client .get (
            f"{CRM_API_BASE_URL }/api/crm/subscriptions/private-channel/invite",
            params ={"user_id":user_key },
            headers ={"Authorization":f"Bearer {CRM_API_TOKEN }"},
            )
        if response .status_code !=200 :
            return None 
        payload =response .json ()
        return payload if isinstance (payload ,dict )else None 
    except Exception as e :
        logger .warning ("Private channel backend request failed: %s",e .__class__ .__name__ )
        return None 


async def _fetch_private_channel_local (user_key :int )->dict |None :
    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            payload =await crm_service .get_private_channel_invite (user_key )
            await session .commit ()
            return payload
    except Exception as e :
        logger .warning ("Private channel local request failed: %s",e .__class__ .__name__ )
        return None 


async def _get_private_channel_payload (tg_id :int )->dict |None :
    payload =await _fetch_private_channel_from_backend (tg_id )
    if payload is not None :
        return payload
    return await _fetch_private_channel_local (tg_id )


def _short_text (value :str |None ,limit :int =420 )->str :
    if not value :
        return "РћРїРёСЃР°РЅРёРµ РЅРµ СѓРєР°Р·Р°РЅРѕ."
    text =normalize_text_for_telegram (value )or value 
    if len (text )<=limit :
        return text 
    return text [:limit ].rstrip ()+"..."


def _format_catalog_price (price_value )->str :
    try :
        if price_value is None :
            return "Р¦РµРЅР° РїРѕ Р·Р°РїСЂРѕСЃСѓ"
        price =int (float (price_value ))
        if price <=0 :
            return "Р‘РµСЃРїР»Р°С‚РЅРѕ"
        return f"{price } в‚Ѕ"
    except Exception :
        return "Р¦РµРЅР° РїРѕ Р·Р°РїСЂРѕСЃСѓ"


def _format_catalog_item_card (item :CatalogItem )->str :
    title =normalize_text_for_telegram (item .title )or "Р‘РµР· РЅР°Р·РІР°РЅРёСЏ"
    description =_short_text (item .description )
    price_text =_format_catalog_price (item .price )
    return (
    f"{title }\n"
    f"рџ’і {price_text }\n\n"
    f"{description }"
    )

GESTALT_SHORT_SCREEN_1 =(
"🧠 *Гештальт-терапия*\n\n"
"Помогает:\n"
"• лучше понимать свои чувства\n"
"• снижать внутреннее напряжение\n"
"• жить осознанно «здесь и сейчас»\n\n"
"Это про живой контакт с собой и людьми,\n"
"а не про советы «как правильно»."
)

GESTALT_SHORT_SCREEN_2 =(
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

ASSISTANT_GREETING =(
"Здравствуйте, я ассистент Ренаты Минаковой, какой у Вас вопрос?"
)

COURSE_ASSISTANT_GREETING =(
"Здравствуйте, я ассистент Ренаты Минаковой. Задайте вопросы о курсе — я расскажу программу, кому подойдет и как записаться.\n\n"
"Примеры вопросов:\n"
"• Какая программа курса?\n"
"• Кому подойдет курс и как записаться?"
)

ONLINE_COURSES_TEXT =(
"Почему я хожу по кругу? Как выйти из детских сценариев, которые управляют вами\n\n"
"\"Чувствуешь вину, когда отдыхаешь?\"\n"
"\"Постоянно спасаешь подруг, а о тебе никто не помнит?\"\n"
"\"В ссорах всегда оказываешься крайним?\"\n"
"Это не твой характер. Это роль \"Козла отпущения\" или \"Героя\", которую тебе навязали в 5 лет. Узнай, как её снять, на лекции-практикуме."
)

GAME10_SCREEN_TEXT =(
"🔥 *«Игра 10:0»*\n\n"
"Ты в закрытом сообществе «Игра 10:0». Здесь ты начнёшь действовать и побеждать. "
"Ты получишь распаковку своей супер-силы в отношениях, карьере, бизнесе, здоровье. "
"Это не просто «поддержка» и «разговоры». А жесткая, но бережная методология, собранная "
"из системной психологии и нейропрактик."
)

GAME10_ASSISTANT_GREETING =(
"*Задайте вопрос про «Игра 10:0»*\n"
"Например:\n"
"• С чего начать в «Игра 10:0»?\n"
"• Что я получу в клубе?\n"
"• Как проходит работа и поддержка?"
)


# ============ Helpers ============

def _reset_states (context :ContextTypes .DEFAULT_TYPE ):
    context .user_data [WAITING_LEAD_KEY ]=None 
    context .user_data [AI_MODE_KEY ]=False 
    context .user_data .pop (ASSISTANT_SOURCE_KEY ,None )
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=False 
    context .user_data [WAITING_CONTACT_EMAIL_KEY ]=False 
    context .user_data .pop (CONTACT_FLOW_KEY ,None )
    context .user_data .pop (CONTACT_PHONE_KEY ,None )
    context .user_data .pop (SKIP_NEXT_EMAIL_KEY ,None )


def _err_name (exc :Exception |None )->str :
    return exc .__class__ .__name__ if exc is not None else "UnknownError"


def _err_short (exc :Exception |None ,limit :int =180 )->str :
    if exc is None :
        return ""
    text =str (exc ).replace ("\r"," ").replace ("\n"," ").strip ()
    if len (text )>limit :
        text =text [:limit ]+"..."
    return text


def _log_db_issue (scope :str ,exc :Exception |None =None )->None :
    short =_err_short (exc )
    if short :
        logger .warning ("DB issue [%s]: %s: %s",scope ,_err_name (exc ),short )
    else :
        logger .warning ("DB issue [%s]: %s",scope ,_err_name (exc ))


def _remember_pending_contacts (context :ContextTypes .DEFAULT_TYPE ,update :Update ,*,phone :str |None =None ,email :str |None =None )->dict :
    pending =dict (context .user_data .get (PENDING_CONTACTS_KEY )or {})
    tg_user =update .effective_user 
    if tg_user is not None :
        pending ["tg_id"]=int (tg_user .id )
        if tg_user .username :
            pending ["username"]=tg_user .username 
        name_parts =[tg_user .first_name or "",tg_user .last_name or ""]
        full_name =" ".join (part for part in name_parts if part ).strip ()
        if full_name :
            pending ["name"]=full_name 
    if phone :
        pending ["phone"]=phone 
    if email :
        pending ["email"]=email 
    pending ["updated_at"]=datetime .utcnow ().isoformat ()
    context .user_data [PENDING_CONTACTS_KEY ]=pending 
    return pending 


async def _notify_admin_pending_contacts (context :ContextTypes .DEFAULT_TYPE ,payload :dict ):
    if not ADMIN_CHAT_ID :
        return 
    try :
        tg_id =payload .get ("tg_id")or "-"
        username =str (payload .get ("username")or "-").strip ()
        name =str (payload .get ("name")or "-").strip ()
        phone =str (payload .get ("phone")or "-").strip ()
        email =str (payload .get ("email")or "-").strip ()
        user_line =f"@{username }" if username and username !="-" else "-"
        text =(
        "\u041a\u043e\u043d\u0442\u0430\u043a\u0442\u044b \u043f\u0440\u0438\u043d\u044f\u0442\u044b (fallback \u0431\u0435\u0437 \u0411\u0414).\n"
        f"tg_id: {tg_id }\n"
        f"username: {user_line }\n"
        f"name: {name }\n"
        f"phone: {phone }\n"
        f"email: {email }"
        )
        await _send (context .bot ,chat_id =int (ADMIN_CHAT_ID ),text =text )
    except Exception as e :
        _log_db_issue ("contacts_admin_notify",e )


async def _notify_db_unavailable (update :Update ,exc :Exception |None =None ,*,scope :str ="db" ):
    _log_db_issue (scope ,exc )
    text ="\u0422\u0435\u0445\u0440\u0430\u0431\u043e\u0442\u044b \u0441 \u0431\u0430\u0437\u043e\u0439. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435."
    keyboard =get_retry_kb ()

    if update .callback_query :
        try :
            await _answer (update .callback_query )
            await _edit (update .callback_query ,text ,reply_markup =keyboard )
            return 
        except Exception as notify_exc :
            _log_db_issue ("notify_db_unavailable_edit",notify_exc )

    if update .effective_message :
        await _reply (update .effective_message ,text ,reply_markup =keyboard )


async def ensure_user (update :Update ,source :str ="bot",ai_increment :int =0 ):
    """
    Р•РґРёРЅР°СЏ С‚РѕС‡РєР°: СЃРѕР·РґР°С‘Рј/РѕР±РЅРѕРІР»СЏРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р‘Р” РїРѕ tg_id.
    Р’РѕР·РІСЂР°С‰Р°РµС‚ РѕР±СЉРµРєС‚ User (РёР· Р‘Р”).
    """
    tg_user =update .effective_user 
    if tg_user is None :
        return None 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            user_service =UserService (session )
            user =await user_service .get_or_create_by_tg_id (
            tg_id =tg_user .id ,
            first_name =tg_user .first_name ,
            last_name =tg_user .last_name ,
            username =tg_user .username ,
            source =source ,
            update_if_exists =True ,
            )
            now =datetime .utcnow ()
            if not user .crm_stage :
                user .crm_stage =User .CRM_STAGE_NEW 
            user .crm_stage =CRMService .stage_after_message (user .crm_stage )
            user .last_activity_at =now 
            user .updated_at =now 

            activity_service =ActivityService (session )
            await activity_service .upsert (
            user_id =user .id ,
            last_activity_at =now ,
            ai_increment =ai_increment ,
            )
            await session .commit ()
            return user 
    except Exception as e :
        logger .exception ("РћС€РёР±РєР° Р‘Р” РІ ensure_user: %s",e )
        await _notify_db_unavailable (update )
        return None 


        # ============ Handlers ============

async def ensure_user_on_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .get (CONTACT_FLOW_KEY ):
        return
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return
    await ensure_user (update ,source ="bot")


async def start (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
# РіР°СЂР°РЅС‚РёСЂСѓРµРј РЅР°Р»РёС‡РёРµ user РІ Р‘Р”
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    screen_manager .clear_screen (context )
    _reset_states (context )

    text ="РђСЃСЃРёСЃС‚РµРЅС‚ РіРѕС‚РѕРІ РїРѕРјРѕС‡СЊ СЃ... рџ‘‡"
    await _show_screen (update ,context ,text ,reply_markup =get_main_menu ())


async def main_menu (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )
    await _show_screen (update ,context ,"рџ“‹ Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ",reply_markup =get_main_menu ())


async def show_contacts_request (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    _reset_states (context )
    context .user_data [CONTACT_FLOW_KEY ]=True 
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=True 

    await _show_screen (
    update ,
    context ,
    "\u041e\u0441\u0442\u0430\u0432\u044c\u0442\u0435, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u043d\u043e\u043c\u0435\u0440 \u0442\u0435\u043b\u0435\u0444\u043e\u043d\u0430 \u043a\u043d\u043e\u043f\u043a\u043e\u0439 \u043d\u0438\u0436\u0435, \u0437\u0430\u0442\u0435\u043c \u044f \u043f\u043e\u043f\u0440\u043e\u0448\u0443 \u043f\u043e\u0447\u0442\u0443.",
    reply_markup =get_contact_request_kb (),
    )


async def contact_manager (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    if query :
        await _answer (query )

    _reset_states (context )
    text =(
    "\u0421\u0432\u044f\u0436\u0443 \u0441 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u043e\u043c.\n"
    "\u041e\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b \u2014 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u0441\u0432\u044f\u0436\u0435\u0442\u0441\u044f \u0441 \u0432\u0430\u043c\u0438 \u0432 \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0435\u0435 \u0432\u0440\u0435\u043c\u044f."
    )
    await _show_screen (update ,context ,text ,reply_markup =get_contact_manager_kb ())


async def _save_contacts (update :Update ,context :ContextTypes .DEFAULT_TYPE ,phone :str ,email :str ):
    tg_user =update .effective_user 
    if tg_user is None :
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            result =await crm_service .update_client_contacts (
            tg_id =tg_user .id ,
            phone =phone ,
            email =email ,
            )
            if result is None :
                user_service =UserService (session )
                await user_service .get_or_create_by_tg_id (
                tg_id =tg_user .id ,
                first_name =tg_user .first_name ,
                last_name =tg_user .last_name ,
                username =tg_user .username ,
                source ="bot",
                update_if_exists =True ,
                )
                await crm_service .update_client_contacts (
                tg_id =tg_user .id ,
                phone =phone ,
                email =email ,
                )
            await session .commit ()
    except Exception as e :
        _log_db_issue ("save_contacts",e )
        pending =_remember_pending_contacts (context ,update ,phone =phone ,email =email )
        await _notify_admin_pending_contacts (context ,pending )
        _reset_states (context )
        await _show_screen (
        update ,
        context ,
        "\u2705 \u041a\u043e\u043d\u0442\u0430\u043a\u0442\u044b \u043f\u0440\u0438\u043d\u044f\u0442\u044b. \u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u0441\u0432\u044f\u0436\u0435\u0442\u0441\u044f \u0441 \u0432\u0430\u043c\u0438 \u0432 \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0435\u0435 \u0432\u0440\u0435\u043c\u044f.",
        reply_markup =get_back_to_menu_kb (),
        )
        return 

    _reset_states (context )
    context .user_data .pop (PENDING_CONTACTS_KEY ,None )
    await _show_screen (
    update ,
    context ,
    "\u2705 \u041e\u0442\u043b\u0438\u0447\u043d\u043e, \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b. \u041c\u044b \u0441\u043a\u043e\u0440\u043e \u0441\u0432\u044f\u0436\u0435\u043c\u0441\u044f \u0441 \u0432\u0430\u043c\u0438.",
    reply_markup =get_back_to_menu_kb (),
    )


async def _get_contact_snapshot (tg_id :int )->dict |None :
    try :
        db .init_db ()
        async with db .async_session ()as session :
            row =await session .execute (
            select (User .id ,User .phone ,User .email ).where (User .tg_id ==tg_id )
            )
            data =row .first ()
            if data is None :
                return None 
            return {"id":int (data [0 ]),"phone":data [1 ],"email":data [2 ]}
    except Exception as e :
        _log_db_issue ("contact_snapshot",e )
        return None 


async def _save_contact_field (update :Update ,context :ContextTypes .DEFAULT_TYPE ,*,phone :str |None =None ,email :str |None =None )->bool :
    tg_user =update .effective_user 
    if tg_user is None :
        return False 
    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            result =await crm_service .update_client_contacts (
            tg_id =tg_user .id ,
            phone =phone ,
            email =email ,
            )
            if result is None :
                user_service =UserService (session )
                await user_service .get_or_create_by_tg_id (
                tg_id =tg_user .id ,
                first_name =tg_user .first_name ,
                last_name =tg_user .last_name ,
                username =tg_user .username ,
                source ="bot",
                update_if_exists =True ,
                )
                await crm_service .update_client_contacts (
                tg_id =tg_user .id ,
                phone =phone ,
                email =email ,
                )
            await session .commit ()
        return True 
    except Exception as e :
        _log_db_issue ("save_contact_field",e )
        _remember_pending_contacts (context ,update ,phone =phone ,email =email )
        return True 


async def handle_contact_phone (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if not update .message or not update .message .contact :
        return 

    waiting_phone =bool (context .user_data .get (WAITING_CONTACT_PHONE_KEY ))
    if not waiting_phone :
        tg_user =update .effective_user 
        if tg_user is None :
            return 
        snapshot =await _get_contact_snapshot (tg_user .id )
        if snapshot is None :
            return 
        if snapshot .get ("phone")and snapshot .get ("email"):
            await _show_screen (update ,context ,'Контакты уже получены, спасибо!',reply_markup =get_main_menu ())
            return 

    contact =update .message .contact 
    phone =(contact .phone_number or "").strip ()
    if not phone :
        await _show_screen (update ,context ,'Не удалось прочитать номер. Отправьте контакт ещё раз.',reply_markup =get_contact_request_kb ())
        return 
    if not await _save_contact_field (update ,context ,phone =phone ):
        return 

    context .user_data [CONTACT_PHONE_KEY ]=phone 
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=False 
    context .user_data [WAITING_CONTACT_EMAIL_KEY ]=True 
    context .user_data [SKIP_NEXT_EMAIL_KEY ]=True 
    await _show_screen (update ,context ,'Спасибо! Теперь пришлите вашу почту одним сообщением (например: name@example.com).',reply_markup =get_remove_reply_kb ())


async def handle_contact_phone_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if not context .user_data .get (WAITING_CONTACT_PHONE_KEY ):
        return 
    if not update .message or not update .message .text :
        return 

    text =(update .message .text or "").strip ()
    if text .lower ()=="отмена":
        _reset_states (context )
        await _show_screen (update ,context ,'Действие отменено.',reply_markup =get_main_menu ())
        return 

    normalized =re .sub (r"[^\\d+]","",text )
    if len (re .sub (r"\\D","",normalized ))<10 :
        await _show_screen (update ,context ,'Номер выглядит некорректно. Пример: +79991234567',reply_markup =get_contact_request_kb ())
        return 
    if not await _save_contact_field (update ,context ,phone =normalized ):
        return 

    context .user_data [CONTACT_PHONE_KEY ]=normalized 
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=False 
    context .user_data [WAITING_CONTACT_EMAIL_KEY ]=True 
    context .user_data [SKIP_NEXT_EMAIL_KEY ]=True 
    await _show_screen (update ,context ,'Спасибо! Теперь пришлите вашу почту одним сообщением (например: name@example.com).',reply_markup =get_remove_reply_kb ())


async def handle_contact_email_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .pop (SKIP_NEXT_EMAIL_KEY ,False ):
        return 
    if not update .message or not update .message .text :
        return 

    waiting_email =bool (context .user_data .get (WAITING_CONTACT_EMAIL_KEY ))
    email =(update .message .text or "").strip ().lower ()
    if waiting_email and email =="отмена":
        _reset_states (context )
        await _show_screen (update ,context ,'Действие отменено.',reply_markup =get_main_menu ())
        return 

    if not EMAIL_RE .match (email ):
        if waiting_email :
            await _show_screen (update ,context ,'Некорректный email. Пример: name@example.com',reply_markup =get_remove_reply_kb ())
        return 

    tg_user =update .effective_user 
    if tg_user is None :
        return 

    snapshot =await _get_contact_snapshot (tg_user .id )
    if snapshot is not None and snapshot .get ("phone")and snapshot .get ("email"):
        _reset_states (context )
        await _show_screen (update ,context ,'Контакты уже получены, спасибо!',reply_markup =get_main_menu ())
        return 

    phone =context .user_data .get (CONTACT_PHONE_KEY )
    if not phone and snapshot is not None :
        phone =snapshot .get ("phone")
    if not phone :
        if waiting_email :
            context .user_data [WAITING_CONTACT_EMAIL_KEY ]=False 
            context .user_data [WAITING_CONTACT_PHONE_KEY ]=True 
        await _show_screen (update ,context ,'Сначала отправьте номер телефона.',reply_markup =get_contact_request_kb ())
        return 

    await _save_contacts (update ,context ,phone =phone ,email =email )


def _set_screen_meta (context :ContextTypes .DEFAULT_TYPE ,*,kind :str ,event_id :int |None =None )->None :
    context .user_data [SCREEN_KIND_KEY ]=kind
    if event_id is None :
        context .user_data .pop (SCREEN_EVENT_ID_KEY ,None )
    else :
        context .user_data [SCREEN_EVENT_ID_KEY ]=int (event_id )


def _safe_json_list (value ):
    if isinstance (value ,list ):
        return value
    if isinstance (value ,str ):
        try :
            parsed =json .loads (value )
            return parsed if isinstance (parsed ,list )else None
        except Exception :
            return None
    return None


def _format_rub (value )->str :
    try :
        amount =int (float (value ))
    except Exception :
        return str (value )
    return f"{amount :,}".replace (","," ")


def _event_prices_lines (event :dict )->list [str ]:
    pricing_options =_safe_json_list (event .get ("pricing_options"))or []
    lines :list [str ]=[]
    for item in pricing_options :
        if not isinstance (item ,dict ):
            continue
        label =str (item .get ("label")or "\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c").strip ()
        price_rub =item .get ("price_rub")
        if price_rub in (None ,""):
            continue
        note =str (item .get ("note")or "").strip ()
        line =f"\u2022 {label} — {_format_rub (price_rub )} \u20bd"
        if note :
            line =f"{line} ({note })"
        lines .append (line )
    if lines :
        return lines
    fallback_price =event .get ("price")
    if fallback_price not in (None ,""):
        return [f"\u2022 \u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c — {_format_rub (fallback_price )} \u20bd"]
    return []


def _event_schedule_label (event :dict )->str :
    schedule_type =str (event .get ("schedule_type")or "").strip ().lower ()
    schedule_text =str (event .get ("schedule_text")or "").strip ()
    if schedule_text :
        return schedule_text
    if schedule_type =="rolling":
        return "\u0414\u0430\u0442\u0430 \u0443\u0442\u043e\u0447\u043d\u044f\u0435\u0442\u0441\u044f"
    date_value =str (event .get ("date")or "").strip ()
    if date_value :
        return date_value
    return "\u0414\u0430\u0442\u0430 \u0443\u0442\u043e\u0447\u043d\u044f\u0435\u0442\u0441\u044f"


def _truncate_plain_text (value :str ,limit :int =1000 )->str :
    normalized =(value or "").replace ("\r\n","\n").strip ()
    if len (normalized )<=limit :
        return normalized
    return normalized [:max (0 ,limit -1 )].rstrip ()+"\u2026"


def _build_events_list_keyboard (events :list [dict ],page :int )->InlineKeyboardMarkup :
    start =page *EVENTS_LIST_PAGE_SIZE
    end =start +EVENTS_LIST_PAGE_SIZE
    rows :list [list [InlineKeyboardButton ]]=[]
    for event in events [start :end ]:
        title =str (event .get ("title")or f"\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435 #{event .get ('id')}")
        title =title .strip ()or f"\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435 #{event .get ('id')}"
        if len (title )>64 :
            title =title [:61 ]+"\u2026"
        rows .append ([InlineKeyboardButton (title ,callback_data =f"event_open:{event ['id']}")])

    nav :list [InlineKeyboardButton ]=[]
    if page >0 :
        nav .append (InlineKeyboardButton ("\u25c0",callback_data ="event_list_prev"))
    if end <len (events ):
        nav .append (InlineKeyboardButton ("\u25b6",callback_data ="event_list_next"))
    if nav :
        rows .append (nav )
    rows .append ([
    InlineKeyboardButton ("\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c",callback_data ="event_list_refresh"),
    InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu"),
    ])
    return InlineKeyboardMarkup (rows )


def _build_event_detail_keyboard (event_id :int )->InlineKeyboardMarkup :
    return InlineKeyboardMarkup ([
    [InlineKeyboardButton ("\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c\u0441\u044f",callback_data =f"event_register:{event_id}")],
    [InlineKeyboardButton ("\u0412\u043e\u043f\u0440\u043e\u0441\u044b \u043a \u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442\u0443",callback_data =f"event_questions:{event_id}")],
    [
    InlineKeyboardButton ("\u041d\u0430\u0437\u0430\u0434 \u043a \u0441\u043f\u0438\u0441\u043a\u0443",callback_data ="events_list"),
    InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu"),
    ],
    ])


def _build_event_detail_text (event :dict )->str :
    title =str (event .get ("title")or "\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435").strip ()
    lines =[
    title ,
    "",
    f"\U0001f4c5 {_event_schedule_label (event )}",
    ]
    location =str (event .get ("location")or "").strip ()
    if location :
        lines .append (f"\U0001f4cd {location }")
    hosts =str (event .get ("hosts")or "").strip ()
    if hosts :
        hosts_line =hosts .replace ("\r\n","\n").strip ()
        lines .append (f"\U0001f3a4 \u0412\u0435\u0434\u0443\u0449\u0438\u0435: {hosts_line }")
    price_lines =_event_prices_lines (event )
    if price_lines :
        lines .append ("\U0001f4b3 \u0426\u0435\u043d\u044b:")
        lines .extend (price_lines )
    description =_truncate_plain_text (str (event .get ("description")or ""),limit =1000 )
    if description :
        lines .append ("")
        lines .append ("\U0001f4dd "+description )
    return "\n".join (lines )[:3500 ]


def _event_ai_context_text (event :dict |None )->str :
    if not isinstance (event ,dict ):
        return ""
    parts :list [str ]=[]
    title =str (event .get ("title")or "").strip ()
    if title :
        parts .append (f"\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435: {title }")
    parts .append (f"\u0420\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0435: {_event_schedule_label (event )}")
    location =str (event .get ("location")or "").strip ()
    if location :
        parts .append (f"\u041b\u043e\u043a\u0430\u0446\u0438\u044f: {location }")
    hosts =str (event .get ("hosts")or "").strip ()
    if hosts :
        parts .append (f"\u0412\u0435\u0434\u0443\u0449\u0438\u0435: {hosts }")
    price_lines =_event_prices_lines (event )
    if price_lines :
        parts .append ("\u0426\u0435\u043d\u044b:\n"+"\n".join (price_lines ))
    description =_truncate_plain_text (str (event .get ("description")or ""),limit =700 )
    if description :
        parts .append (f"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435: {description }")
    return "\n".join (parts )


def _get_cached_events (context :ContextTypes .DEFAULT_TYPE )->list [dict ]:
    cached =context .user_data .get (EVENTS_CACHE_KEY )
    return cached if isinstance (cached ,list )else []


def _find_cached_event (context :ContextTypes .DEFAULT_TYPE ,event_id :int )->dict |None :
    for item in _get_cached_events (context ):
        try :
            if int (item .get ("id"))==int (event_id ):
                return item
        except Exception :
            continue
    return None


async def _load_events_cache (update :Update ,context :ContextTypes .DEFAULT_TYPE ,*,force_refresh :bool =False )->list [dict ]|None :
    if not force_refresh :
        cached =context .user_data .get (EVENTS_CACHE_KEY )
        if isinstance (cached ,list ):
            return cached
    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            result =await crm_service .list_active_events ()
            items =result .get ("items",[])
            events =items if isinstance (items ,list )else []
            context .user_data [EVENTS_CACHE_KEY ]=events
            return events
    except Exception as e :
        logger .exception ("Events cache load failed: %s",e )
        await _notify_db_unavailable (update )
        return None


async def show_events_list_screen (update :Update ,context :ContextTypes .DEFAULT_TYPE ,*,force_refresh :bool =False ,page :int |None =None ):
    events =await _load_events_cache (update ,context ,force_refresh =force_refresh )
    if events is None :
        return
    if not events :
        context .user_data [EVENTS_LIST_PAGE_KEY ]=0
        _set_screen_meta (context ,kind ="events_list")
        await _show_screen (update ,context ,"\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u044b\u0445 \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0439.",reply_markup =InlineKeyboardMarkup ([
        [InlineKeyboardButton ("\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c",callback_data ="event_list_refresh")],
        [InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
        ]))
        return

    total_pages =max (1 ,(len (events )+EVENTS_LIST_PAGE_SIZE -1 )//EVENTS_LIST_PAGE_SIZE )
    if page is None :
        page =int (context .user_data .get (EVENTS_LIST_PAGE_KEY )or 0 )
    page =max (0 ,min (int (page ),total_pages -1 ))
    context .user_data [EVENTS_LIST_PAGE_KEY ]=page
    text ="Выберите мероприятие 👇"
    if total_pages >1 :
        text =f"{text }\n\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0430 {page +1 }/{total_pages }"
    _set_screen_meta (context ,kind ="events_list")
    await _show_screen (update ,context ,text ,reply_markup =_build_events_list_keyboard (events ,page ))


async def show_event_detail_screen (update :Update ,context :ContextTypes .DEFAULT_TYPE ,event_id :int ,*,force_refresh :bool =False ):
    events =await _load_events_cache (update ,context ,force_refresh =force_refresh )
    if events is None :
        return
    event =_find_cached_event (context ,event_id )
    if event is None and not force_refresh :
        return await show_event_detail_screen (update ,context ,event_id ,force_refresh =True )
    if event is None :
        _set_screen_meta (context ,kind ="events_list")
        await _show_screen (update ,context ,"\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e.",reply_markup =InlineKeyboardMarkup ([
        [InlineKeyboardButton ("\u041a \u0441\u043f\u0438\u0441\u043a\u0443",callback_data ="events_list")],
        [InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
        ]))
        return
    _set_screen_meta (context ,kind ="event_detail",event_id =event_id )
    await _show_screen (update ,context ,_build_event_detail_text (event ),reply_markup =_build_event_detail_keyboard (event_id ))


async def events_list_callback (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    await show_events_list_screen (update ,context )


async def event_list_refresh (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    await show_events_list_screen (update ,context ,force_refresh =True )


async def event_list_next (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    page =int (context .user_data .get (EVENTS_LIST_PAGE_KEY )or 0 )+1
    await show_events_list_screen (update ,context ,page =page )


async def event_list_prev (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    page =int (context .user_data .get (EVENTS_LIST_PAGE_KEY )or 0 )-1
    await show_events_list_screen (update ,context ,page =page )


async def event_open (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    try :
        event_id =int ((query .data or "").split (":",1 )[1 ])
    except Exception :
        await _show_screen (update ,context ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435.",reply_markup =InlineKeyboardMarkup ([
        [InlineKeyboardButton ("\u041a \u0441\u043f\u0438\u0441\u043a\u0443",callback_data ="events_list")],
        [InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
        ]))
        return
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    await show_event_detail_screen (update ,context ,event_id )


async def event_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    try :
        event_id =int ((query .data or "").split (":",1 )[1 ])
    except Exception :
        await _show_screen (update ,context ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0447\u0430\u0442 \u043f\u043e \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044e.",reply_markup =get_back_to_menu_kb ())
        return
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return
    user_id =update .effective_user .id
    chat_histories [user_id ]=[]
    context .user_data [WAITING_LEAD_KEY ]=None
    context .user_data [AI_MODE_KEY ]=True
    context .user_data [ASSISTANT_SOURCE_KEY ]="event"
    context .user_data [ASSISTANT_EVENT_ID_KEY ]=event_id
    event =_find_cached_event (context ,event_id )
    if event is None :
        await _load_events_cache (update ,context ,force_refresh =True )
        event =_find_cached_event (context ,event_id )
    title =str ((event or {}).get ("title")or "").strip ()
    prompt ="\u0417\u0430\u0434\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441 \u043f\u043e \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044e \u2014 \u044f \u043f\u043e\u043c\u043e\u0433\u0443 \u043f\u043e \u0440\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u044e, \u0444\u043e\u0440\u043c\u0430\u0442\u0443 \u0438 \u0437\u0430\u043f\u0438\u0441\u0438."
    if title :
        prompt =f"\u0412\u043e\u043f\u0440\u043e\u0441\u044b \u043f\u043e \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044e: {title }\n\n{prompt }"
    await _show_screen (update ,context ,prompt ,reply_markup =get_back_to_menu_kb ())



    # --------- Events ---------

async def show_events (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _send_events_list (update ,user_db ,context ,from_callback =True )


async def show_events_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 
    await _send_events_list (update ,user_db ,context ,from_callback =False )


async def show_courses (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _send_courses_list (update ,context ,offset =0 ,from_callback =True )


async def show_courses_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 
    await _send_courses_list (update ,context ,offset =0 ,from_callback =False )


async def show_courses_page (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    try :
        offset =int ((query .data or "").split (":")[1 ])
    except Exception :
        offset =0 

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _send_courses_list (update ,context ,offset =max (offset ,0 ),from_callback =True )


async def show_private_channel (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _show_screen (
    update ,
    context ,
    GAME10_SCREEN_TEXT ,
    parse_mode ="Markdown",
    reply_markup =get_game10_kb (_private_channel_payment_url ()),
    )


async def private_channel_payment_info (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _ =context 
    query =update .callback_query 
    if query is None :
        return 
    await _answer (query ,"Ссылка на оплату временно недоступна. Нажмите «Связаться с менеджером».",show_alert =True )


    # --------- Consultations / Gestalt ---------

async def show_consultations (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _show_screen (update ,context ,
    GESTALT_SHORT_SCREEN_1 ,
    parse_mode ="Markdown",
    reply_markup =get_consultations_menu (),
    )


async def show_formats_and_prices (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _show_screen (update ,context ,
    GESTALT_SHORT_SCREEN_2 ,
    parse_mode ="Markdown",
    reply_markup =get_consultation_formats_menu (),
    )


async def begin_booking_individual (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    context .user_data [AI_MODE_KEY ]=False 
    context .user_data [WAITING_LEAD_KEY ]="individual"

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _show_screen (update ,context ,
    "📩 *Запись на индивидуальную терапию*\n\n"
    "Отправьте одним сообщением:\n"
    "1) Имя\n"
    "2) Телефон или @username\n"
    "3) Коротко запрос (по желанию)\n\n"
    "Пример: Иван, +46..., хочу меньше тревоги",
    parse_mode ="Markdown",
    reply_markup =get_back_to_menu_kb (),
    )


async def begin_booking_group (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    context .user_data [AI_MODE_KEY ]=False 
    context .user_data [WAITING_LEAD_KEY ]="group"

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    await _show_screen (update ,context ,
    "📩 *Запись в терапевтическую группу*\n\n"
    "Отправьте одним сообщением:\n"
    "1) Имя\n"
    "2) Телефон или @username\n"
    "3) Коротко ожидания от группы (по желанию)\n\n"
    "Пример: Анна, @anna, хочу научиться говорить о чувствах",
    parse_mode ="Markdown",
    reply_markup =get_back_to_menu_kb (),
    )


async def handle_lead_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    """Lead request handler when WAITING_LEAD is active."""
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return 

    mode =context .user_data .get (WAITING_LEAD_KEY )
    if not mode :
        return 

    text =(update .message .text or "").strip ()
    if not text :
        await _reply (update .message ,"\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0442\u0435\u043a\u0441\u0442\u043e\u043c, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430.")
        return 

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    user =update .effective_user 
    if user is None :
        return 

    lead_type ="\u0418\u043d\u0434\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d\u043e"if mode =="individual"else "\u0413\u0440\u0443\u043f\u043f\u0430"

    lead_payload =(
    f"NEW lead: *{lead_type }*\n"
    f"user: {user .first_name } {user .last_name or ''} (@{user .username or '-'})\n"
    f"tg_id: `{user .id }`\n\n"
    f"message:\n{text }"
    )

    context .user_data [WAITING_LEAD_KEY ]=None 

    if ADMIN_CHAT_ID :
        try :
            await _send (context .bot ,
            chat_id =int (ADMIN_CHAT_ID ),
            text =lead_payload ,
            parse_mode ="Markdown",
            )
        except Exception as e :
            logger .exception ("Lead notify admin failed: %s",e )

    await _show_screen (
    update ,
    context ,
    "\u2705 \u0421\u043f\u0430\u0441\u0438\u0431\u043e! \u0417\u0430\u044f\u0432\u043a\u0430 \u043f\u0440\u0438\u043d\u044f\u0442\u0430. \u041c\u044b \u0441\u043a\u043e\u0440\u043e \u0441\u0432\u044f\u0436\u0435\u043c\u0441\u044f.",
    reply_markup =get_back_to_menu_kb (),
    )





    # --------- AI ---------

async def show_ai_chat (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    user_id =update .effective_user .id 
    chat_histories [user_id ]=[]# СЃР±СЂР°СЃС‹РІР°РµРј РёСЃС‚РѕСЂРёСЋ РїСЂРё РІС…РѕРґРµ

    context .user_data [WAITING_LEAD_KEY ]=None 
    context .user_data [AI_MODE_KEY ]=True 
    context .user_data .pop (ASSISTANT_SOURCE_KEY ,None )
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )

    await _show_screen (update ,context ,
    ASSISTANT_GREETING ,
    reply_markup =get_back_to_menu_kb (),
    )


async def show_course_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    user_id =update .effective_user .id 
    chat_histories [user_id ]=[]

    context .user_data [WAITING_LEAD_KEY ]=None 
    context .user_data [AI_MODE_KEY ]=True 
    context .user_data [ASSISTANT_SOURCE_KEY ]="course"
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )

    await _show_screen (
    update ,
    context ,
    COURSE_ASSISTANT_GREETING ,
    reply_markup =get_back_to_menu_kb (),
    )


async def game10_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return

    user_id =update .effective_user .id
    chat_histories [user_id ]=[]

    context .user_data [WAITING_LEAD_KEY ]=None
    context .user_data [AI_MODE_KEY ]=True
    context .user_data [ASSISTANT_SOURCE_KEY ]="game10"
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )

    await _show_screen (
    update ,
    context ,
    GAME10_ASSISTANT_GREETING ,
    parse_mode ="Markdown",
    reply_markup =get_back_to_menu_kb (),
    )


async def _show_consultations_from_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 
    message =update .effective_message 
    if message is not None :
        await _show_screen (update ,context ,"Выберите формат консультации 👇",reply_markup =get_consultations_menu ())


async def _route_detected_intent (update :Update ,context :ContextTypes .DEFAULT_TYPE ,intent :str )->bool :
    if intent =="MENU":
        await menu_command (update ,context )
        return True 
    if intent =="MANAGER":
        await contact_manager (update ,context )
        return True 
    if intent =="EVENTS":
        await show_events_command (update ,context )
        return True 
    if intent =="COURSES":
        await show_courses_command (update ,context )
        return True 
    if intent =="CONSULT":
        await _show_consultations_from_text (update ,context )
        return True 
    return False 


async def handle_ai_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    """
    AI РѕС‚РІРµС‡Р°РµС‚ С‚РѕР»СЊРєРѕ РІ СЂРµР¶РёРјРµ AI_MODE.
    Р”Р°РЅРЅС‹Рµ Рѕ РјРµСЂРѕРїСЂРёСЏС‚РёСЏС… РїРѕРґС‚СЏРіРёРІР°СЋС‚СЃСЏ РІ core.ai (PostgreSQL).
    """
    # 1) РµСЃР»Рё Р¶РґС‘Рј Р·Р°СЏРІРєСѓ вЂ” AI РЅРµ РЅСѓР¶РµРЅ
    if context .user_data .get (WAITING_LEAD_KEY ):
        return 
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return 

        # 2) РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РІ AI-СЂРµР¶РёРјРµ вЂ” РЅРµ РїРµСЂРµС…РІР°С‚С‹РІР°РµРј С‚РµРєСЃС‚
    if not context .user_data .get (AI_MODE_KEY ):
        return 

        # РіР°СЂР°РЅС‚РёСЂСѓРµРј user (С‡С‚РѕР±С‹ РїРѕС‚РѕРј СЃРѕС…СЂР°РЅСЏС‚СЊ РёСЃС‚РѕСЂРёСЋ/СЃРѕР±С‹С‚РёСЏ/РїР»Р°С‚РµР¶Рё РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ)
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    user_id =update .effective_user .id 
    user_message =(update .message .text or "").strip ()

    if not user_message or user_message .startswith ("/"):
        return 

    intent =detect_intent (user_message )
    if intent in {"MENU","MANAGER"}:
        context .user_data [AI_MODE_KEY ]=False 
        context .user_data [WAITING_LEAD_KEY ]=None 
        context .user_data .pop (ASSISTANT_SOURCE_KEY ,None )
        await _route_detected_intent (update ,context ,intent )
        return 

    typing_indicator =None 
    if context .user_data .get (AI_MODE_KEY )and update .effective_chat is not None :
        typing_indicator =TypingIndicator (context .bot ,update .effective_chat .id )
        await typing_indicator .start ()

    try :
        history =chat_histories .get (user_id ,[])
        assistant_source =str (context .user_data .get (ASSISTANT_SOURCE_KEY )or "").strip ().lower ()
        ai_message =user_message 
        if assistant_source =="course":
            ai_message =f"Контекст: вопросы о курсе GetCourse.\n{user_message }"
        elif assistant_source =="game10":
            ai_message =f"[FOCUS:GAME10]\n{user_message }"
        elif assistant_source =="event":
            event_context =""
            try :
                event_id =context .user_data .get (ASSISTANT_EVENT_ID_KEY )
                if event_id is not None :
                    event_context =_event_ai_context_text (_find_cached_event (context ,int (event_id )))
            except Exception :
                event_context =""
            if event_context :
                ai_message =(
                "\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442: \u0432\u043e\u043f\u0440\u043e\u0441 \u043f\u043e \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044e.\n"
                f"{event_context }\n\n"
                f"\u0412\u043e\u043f\u0440\u043e\u0441 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f: {user_message }"
                )
        response ,new_history =await ai_service .chat (
        ai_message ,
        history ,
        tg_id =update .effective_user .id ,
        )
        chat_histories [user_id ]=new_history 
        if user_db is not None :
            async with db .async_session ()as session :
                activity_service =ActivityService (session )
                await activity_service .upsert (
                user_id =user_db .id ,
                last_activity_at =datetime .utcnow (),
                ai_increment =1 ,
                )
                await session .commit ()
        await _reply (update .message ,response )
    except Exception as e :
        logger .exception ("Assistant error: %s",e )
        await _reply (update .message ,"РЎРµР№С‡Р°СЃ РЅРµ РїРѕР»СѓС‡РёР»РѕСЃСЊ РѕС‚РІРµС‚РёС‚СЊ. РџРѕРїСЂРѕР±СѓР№ С‡СѓС‚СЊ РїРѕР·Р¶Рµ.")


    finally :
        if typing_indicator is not None :
            await typing_indicator .stop ()


async def handle_text_outside_assistant (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .get (WAITING_LEAD_KEY ):
        return 
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return 
    if context .user_data .get (AI_MODE_KEY ):
        return 

    message =update .effective_message 
    if message is None :
        return 
    text =(message .text or "").strip ()
    if not text :
        return 

    intent =detect_intent (text )
    if intent :
        routed =await _route_detected_intent (update ,context ,intent )
        if routed :
            return 

    await _show_screen (update ,context ,"Выберите раздел 👇",reply_markup =get_main_menu ())


        # --------- Help ---------

async def show_help (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    text =(
    "📚 *Помощь*\n\n"
    "• /start — перезапуск\n"
    "• 📅 Мероприятия — список ближайших\n"
    "• 🎓 Консультации — гештальт + запись\n"
    "• 🤝 Ассистент Ренаты — вопросы\n\n"
    "Если не получается — напишите сюда, я помогу 🙂"
    )
    await _show_screen (update ,context ,text ,reply_markup =get_back_to_menu_kb (),parse_mode ="Markdown")


async def course_link_unavailable (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query ,"РЎСЃС‹Р»РєР° РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРЅР°, РјС‹ РѕР±РЅРѕРІРёРј РµС‘ РїРѕСЃР»Рµ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё.",show_alert =True )


    # --------- Errors / Retry ---------

async def retry_db (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    if query :
        await _answer (query )
    try :
        async def _ping_db ():
            db .init_db ()
            async with db .async_session ()as session :
                await session .execute (text ("SELECT 1"))
        await asyncio .wait_for (_ping_db (),timeout =2.0 )
    except Exception as e :
        await _notify_db_unavailable (update ,e ,scope ="retry_db")
        return 

    await _show_screen (update ,context ,"\u2705 \u0411\u0430\u0437\u0430 \u0441\u043d\u043e\u0432\u0430 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430.",reply_markup =get_main_menu ())


async def on_error (update :object ,context :ContextTypes .DEFAULT_TYPE )->None :
    logger .exception ("Unhandled error: %s",context .error )
    if isinstance (update ,Update ):
        await _notify_db_unavailable (update )


async def _send_events_list (
update :Update ,
user_db ,
context :ContextTypes .DEFAULT_TYPE ,
from_callback :bool ,
):
    _ =user_db
    _ =from_callback
    context .user_data [EVENTS_LIST_PAGE_KEY ]=0
    await show_events_list_screen (update ,context ,force_refresh =True )


async def _send_courses_list (
update :Update ,
context :ContextTypes .DEFAULT_TYPE ,
*,
offset :int =0 ,
from_callback :bool ,
):
    _ =context 
    _ =offset 
    message =ONLINE_COURSES_TEXT 
    markup =get_courses_empty_kb ()
    await _show_screen (update ,context ,message ,reply_markup =markup )


async def event_register (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    try :
        event_id =int (query .data .split (":")[1 ])
    except Exception :
        await _answer (query ,"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id 
            result =await crm_service .add_attendee_by_tg_id (event_id ,tg_id )
            if not result .get ("ok")and result .get ("error")=="event_not_found":
                await _answer (query ,"РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ",show_alert =True )
                return 
            if not result .get ("ok")and result .get ("error")=="user_not_found":
                await _answer (query ,"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ",show_alert =True )
                return 
            await session .commit ()
            if str (context .user_data .get (SCREEN_KIND_KEY )or "")=="event_detail"and int (context .user_data .get (SCREEN_EVENT_ID_KEY )or 0 )==event_id :
                await show_event_detail_screen (update ,context ,event_id )
            else :
                await _safe_edit_reply_markup (
                query ,
                reply_markup =get_event_actions_kb (event_id ,registered =True ),
                )
            await _answer (query ,"Р’С‹ Р·Р°РїРёСЃР°РЅС‹!"if not result .get ("already")else "Р’С‹ СѓР¶Рµ Р±С‹Р»Рё Р·Р°РїРёСЃР°РЅС‹")
    except Exception as e :
        logger .exception ("РћС€РёР±РєР° Р‘Р” РІ event_register: %s",e )
        await _notify_db_unavailable (update )


async def event_cancel (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    try :
        event_id =int (query .data .split (":")[1 ])
    except Exception :
        await _answer (query ,"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id 
            result =await crm_service .remove_attendee_by_tg_id (event_id ,tg_id )
            if not result .get ("ok")and result .get ("error")=="event_not_found":
                await _answer (query ,"РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ",show_alert =True )
                return 
            if not result .get ("ok")and result .get ("error")=="user_not_found":
                await _answer (query ,"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ",show_alert =True )
                return 
            await session .commit ()
            if str (context .user_data .get (SCREEN_KIND_KEY )or "")=="event_detail"and int (context .user_data .get (SCREEN_EVENT_ID_KEY )or 0 )==event_id :
                await show_event_detail_screen (update ,context ,event_id )
            else :
                await _safe_edit_reply_markup (
                query ,
                reply_markup =get_event_actions_kb (event_id ,registered =False ),
                )
            await _answer (query ,"Р—Р°РїРёСЃСЊ РѕС‚РјРµРЅРµРЅР°"if result .get ("removed")else "Р’С‹ РЅРµ Р±С‹Р»Рё Р·Р°РїРёСЃР°РЅС‹")
    except Exception as e :
        logger .exception ("РћС€РёР±РєР° Р‘Р” РІ event_cancel: %s",e )
        await _notify_db_unavailable (update )


async def event_pay (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    try :
        event_id =int (query .data .split (":")[1 ])
    except Exception :
        await _answer (query ,"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            event_service =EventService (session )
            event =await event_service .get_by_id (event_id )
            if not event :
                await _answer (query ,"РЎРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ",show_alert =True )
                return 

            price_value =event .price 
            amount =int (price_value )if price_value is not None else 0 
            if amount <=0 :
                await _answer (query ,"РћРїР»Р°С‚Р° РґР»СЏ СЌС‚РѕРіРѕ СЃРѕР±С‹С‚РёСЏ РїРѕРєР° РЅРµРґРѕСЃС‚СѓРїРЅР°",show_alert =True )
                return 

            crm_service =CRMService (session )
            result =await crm_service .create_payment_for_user (
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id ,
            event_id =event_id ,
            amount =amount ,
            source ="yookassa",
            )
            if result is None :
                await _answer (query ,"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ РїР»Р°С‚С‘Р¶",show_alert =True )
                return 

            await session .commit ()

            payment_link =f"https://pay.example.local/yookassa?payment_id={result ['id']}"
            event_link_part =(
            f"\nРЎС‚СЂР°РЅРёС†Р° РјРµСЂРѕРїСЂРёСЏС‚РёСЏ РЅР° GetCourse: {event .link_getcourse }"
            if _is_valid_http_url (event .link_getcourse )
            else ""
            )
            invite_part =(
            f"\nРџРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕРїР»Р°С‚С‹ РІС‹ РїРѕР»СѓС‡РёС‚Рµ РґРѕСЃС‚СѓРї РІ РєР°РЅР°Р»: {TG_PRIVATE_CHANNEL_INVITE_LINK }"
            if TG_PRIVATE_CHANNEL_INVITE_LINK 
            else "\nРџРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕРїР»Р°С‚С‹ РјРµРЅРµРґР¶РµСЂ РѕС‚РїСЂР°РІРёС‚ СЃСЃС‹Р»РєСѓ РІ Р·Р°РєСЂС‹С‚С‹Р№ РєР°РЅР°Р»."
            )
            await _send (context .bot ,
            chat_id =update .effective_chat .id ,
            text =(
            "РџР»Р°С‚РµР¶ СЃРѕР·РґР°РЅ (pending).\n"
            f"РЎСЃС‹Р»РєР° РґР»СЏ РѕРїР»Р°С‚С‹: {payment_link }\n"
            "Р•СЃР»Рё РЅСѓР¶РµРЅ Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ СЃРїРѕСЃРѕР±, РЅР°Р¶РјРёС‚Рµ В«РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РјРµРЅРµРґР¶РµСЂРѕРјВ»."
            f"{event_link_part }"
            f"{invite_part }"
            ),
            )
    except Exception as e :
        logger .exception ("РћС€РёР±РєР° Р‘Р” РІ event_pay: %s",e )
        await _notify_db_unavailable (update )


async def menu_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 
    _reset_states (context )
    if update .effective_message :
        await _show_screen (update ,context ,"\u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e",reply_markup =get_main_menu ())


async def mark_paid_dev (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    message =update .effective_message 
    user =update .effective_user 
    if message is None or user is None :
        return 

    if not ADMIN_CHAT_ID or str (user .id )!=str (ADMIN_CHAT_ID ):
        await _reply (message ,"РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ Р±РѕС‚Р°.")
        return 

    args =context .args or []
    if len (args )!=2 :
        await _reply (message ,"Р¤РѕСЂРјР°С‚: /mark_paid <tg_id> <event_id>")
        return 

    try :
        tg_id =int (args [0 ])
        event_id =int (args [1 ])
    except ValueError :
        await _reply (message ,"tg_id Рё event_id РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ С‡РёСЃР»Р°РјРё.")
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            target_user =await crm_service ._get_user_by_tg_id (tg_id )
            if target_user is None :
                await _reply (message ,"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
                return 

            has_event_id =await crm_service ._payments_has_event_id ()
            payment_id :int |None =None 
            if has_event_id :
                row =await session .execute (
                select (Payment )
                .where (Payment .user_id ==target_user .id )
                .where (Payment .event_id ==event_id )
                .order_by (Payment .created_at .desc ())
                )
                payment =row .scalars ().first ()
                if payment is not None :
                    payment_id =payment .id 
            else :
                row =await session .execute (
                text (
                """
                        SELECT id
                        FROM payments
                        WHERE user_id = :user_id
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                ),
                {"user_id":target_user .id },
                )
                row_map =row .mappings ().first ()
                if row_map is not None :
                    payment_id =int (row_map ["id"])

            if payment_id is None :
                await _reply (message ,"РџР»Р°С‚РµР¶ РЅРµ РЅР°Р№РґРµРЅ.")
                return 

            await crm_service .mark_payment_status (payment_id ,"paid")
            await session .commit ()

        await _reply (message ,
        f"РџР»Р°С‚РµР¶ #{payment_id } РѕС‚РјРµС‡РµРЅ РєР°Рє paid РґР»СЏ tg_id={tg_id }, event_id={event_id }."
        )
        if TG_PRIVATE_CHANNEL_INVITE_LINK :
            await _send (context .bot ,
            chat_id =tg_id ,
            text =(
            "РћРїР»Р°С‚Р° РїРѕРґС‚РІРµСЂР¶РґРµРЅР°. Р’РѕС‚ СЃСЃС‹Р»РєР° РІ Р·Р°РєСЂС‹С‚С‹Р№ РєР°РЅР°Р»:\n"
            f"{TG_PRIVATE_CHANNEL_INVITE_LINK }"
            ),
            )
    except Exception as e :
        logger .exception ("РћС€РёР±РєР° РІ /mark_paid: %s",e )
        await _reply (message ,"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РјРµС‚РёС‚СЊ РѕРїР»Р°С‚Сѓ. РџСЂРѕРІРµСЂСЊС‚Рµ Р»РѕРіРё.")


        # ============ App ============

def build_app ()->Application :
    app =Application .builder ().token (BOT_TOKEN ).build ()

    # Commands
    app .add_handler (CommandHandler ("start",start ))
    app .add_handler (CommandHandler ("menu",menu_command ))
    app .add_handler (CommandHandler ("back",menu_command ))
    app .add_handler (CommandHandler ("cancel",menu_command ))
    app .add_handler (CommandHandler ("events",show_events_command ))
    app .add_handler (CommandHandler ("courses",show_courses_command ))
    app .add_handler (CommandHandler ("catalog",show_courses_command ))
    app .add_handler (CommandHandler ("mark_paid",mark_paid_dev ))

    # Menu callbacks
    app .add_handler (CallbackQueryHandler (main_menu ,pattern ="^main_menu$"))
    app .add_handler (CallbackQueryHandler (main_menu ,pattern ="^menu$"))
    app .add_handler (CallbackQueryHandler (retry_db ,pattern ="^retry_db$"))

    # Sections
    app .add_handler (CallbackQueryHandler (show_events ,pattern ="^events$"))
    app .add_handler (CallbackQueryHandler (events_list_callback ,pattern ="^events_list$"))
    app .add_handler (CallbackQueryHandler (event_list_prev ,pattern ="^event_list_prev$"))
    app .add_handler (CallbackQueryHandler (event_list_next ,pattern ="^event_list_next$"))
    app .add_handler (CallbackQueryHandler (event_list_refresh ,pattern ="^event_list_refresh$"))
    app .add_handler (CallbackQueryHandler (event_open ,pattern ="^event_open:"))
    app .add_handler (CallbackQueryHandler (show_courses ,pattern ="^courses$"))
    app .add_handler (CallbackQueryHandler (show_courses_page ,pattern ="^courses_page:"))
    app .add_handler (CallbackQueryHandler (show_private_channel ,pattern ="^private_channel$"))
    app .add_handler (CallbackQueryHandler (private_channel_payment_info ,pattern ="^private_channel_payment_info$"))
    app .add_handler (CallbackQueryHandler (course_link_unavailable ,pattern ="^course_link_unavailable$"))
    app .add_handler (CallbackQueryHandler (show_consultations ,pattern ="^consultations$"))
    app .add_handler (CallbackQueryHandler (show_formats_and_prices ,pattern ="^consult_formats$"))
    app .add_handler (CallbackQueryHandler (show_ai_chat ,pattern ="^ai_chat$"))
    app .add_handler (CallbackQueryHandler (show_course_questions ,pattern ="^course_questions$"))
    app .add_handler (CallbackQueryHandler (game10_questions ,pattern ="^game10_questions$"))
    app .add_handler (CallbackQueryHandler (event_questions ,pattern ="^event_questions:"))
    app .add_handler (CallbackQueryHandler (show_contacts_request ,pattern ="^share_contacts$"))
    app .add_handler (CallbackQueryHandler (contact_manager ,pattern ="^contact_manager$"))
    app .add_handler (CallbackQueryHandler (show_help ,pattern ="^help$"))
    app .add_handler (CallbackQueryHandler (event_register ,pattern ="^event_register:"))
    app .add_handler (CallbackQueryHandler (event_cancel ,pattern ="^event_cancel:"))
    app .add_handler (CallbackQueryHandler (event_pay ,pattern ="^event_pay:"))

    # Booking
    app .add_handler (CallbackQueryHandler (begin_booking_individual ,pattern ="^book_individual$"))
    app .add_handler (CallbackQueryHandler (begin_booking_group ,pattern ="^book_group$"))

    # Messages routing:
    app .add_handler (MessageHandler (filters .ALL ,ensure_user_on_message ),group =-1 )
    app .add_handler (MessageHandler (filters .CONTACT ,handle_contact_phone ),group =0 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,handle_contact_phone_text ),group =1 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,handle_contact_email_text ),group =2 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,handle_lead_message ),group =3 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,handle_ai_message ),group =4 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,handle_text_outside_assistant ),group =5 )

    app .add_error_handler (on_error )

    return app 


def main ():
    if not BOT_TOKEN :
        raise RuntimeError ("BOT_TOKEN is not set")
    if not _acquire_single_instance_lock ():
        logger .error ("Second bot instance detected. Exiting to avoid Telegram getUpdates conflict.")
        return 

    meta =_instance_meta ()
    logger .info (
    "Bot instance metadata: host=%s pid=%s token_hash=%s lock=%s",
    meta ["host"],
    meta ["pid"],
    meta ["token_hash"],
    LOCK_FILE_PATH ,
    )

    app =build_app ()
    heartbeat_stop =_start_lock_heartbeat (LOCK_FILE_PATH )
    logger .info ("Renata Bot Р·Р°РїСѓС‰РµРЅ. PID=%s",os .getpid ())
    logger .warning ("Polling mode: Р·Р°РїСѓСЃРєР°Р№С‚Рµ С‚РѕР»СЊРєРѕ РѕРґРёРЅ СЌРєР·РµРјРїР»СЏСЂ Р±РѕС‚Р°, РёРЅР°С‡Рµ Р±СѓРґРµС‚ Telegram Conflict.")
    try :
        db .init_db ()
    except Exception as e :
        logger .exception ("DB init failed, bot will run without DB: %s",e )
    try :
        app .run_polling (allowed_updates =Update .ALL_TYPES )
    except Conflict :
        logger .exception (
        "Telegram polling conflict (another getUpdates consumer). host=%s pid=%s token_hash=%s",
        meta ["host"],
        meta ["pid"],
        meta ["token_hash"],
        )
        return 
    finally :
        heartbeat_stop .set ()


if __name__ =="__main__":
    main ()


