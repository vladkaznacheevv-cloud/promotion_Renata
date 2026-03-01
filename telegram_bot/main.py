import os 
import json
import asyncio
import logging 
import re 
import socket 
import hashlib 
import atexit 
import threading 
import time
from io import BytesIO
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
ChatJoinRequestHandler,
MessageHandler ,
ApplicationHandlerStop ,
ContextTypes ,
filters ,
)
from core .users .service import UserService 
from core .users .models import User 
from core .events .service import EventService 
from core .crm .service import CRMService 
from core .crm .models import YooKassaPayment
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
get_game10_description_kb ,
get_payment_contact_choice_kb ,
get_game10_payment_link_kb ,
)
from telegram_bot .text_utils import normalize_text_for_telegram ,looks_like_mojibake ,normalize_ui_reply_markup 
from telegram_bot .text_formatting import format_event_card 
from telegram_bot .lock_utils import get_lock_path ,touch_lock_heartbeat 
from telegram_bot .typing_indicator import TypingIndicator 
from telegram_bot .screen_manager import ScreenManager
from telegram_bot .utils import detect_intent ,detect_product_focus ,apply_focus_timeout_state
from telegram_bot .private_channel_gate import decide_private_channel_join_action
try:
    import qrcode
except Exception:  # pragma: no cover - optional runtime dependency
    qrcode = None

try :
    import fcntl # Linux/WSL containers
except Exception :# pragma: no cover - linux runtime expected
    fcntl =None 

load_dotenv ()
logging .basicConfig (level =logging .INFO )
logger =logging .getLogger (__name__ )

# Reduce noisy logs.
logging .getLogger ("httpx").setLevel (logging .WARNING )
logging .getLogger ("telegram").setLevel (logging .WARNING )
logging .getLogger ("telegram.ext").setLevel (logging .WARNING )

def _env_flag_enabled_default_true (name :str )->bool :
    raw =str (os .getenv (name ,"true")or "").strip ().lower ()
    return raw in {"1","true","yes","y","on"}


def _env_flag_enabled_default_false (name :str )->bool :
    raw =str (os .getenv (name ,"false")or "").strip ().lower ()
    return raw in {"1","true","yes","y","on"}


def _parse_admin_ids ()->set [int ]:
    values :set [int ]=set ()
    raw =str (os .getenv ("BOT_ADMIN_IDS")or "").strip ()
    for item in raw .split (","):
        candidate =item .strip ()
        if not candidate :
            continue
        try :
            values .add (int (candidate ))
        except Exception :
            continue
    if ADMIN_CHAT_ID :
        try :
            values .add (int (str (ADMIN_CHAT_ID ).strip ()))
        except Exception :
            pass
    return values


def _int_env (name :str ,default :int )->int :
    raw =str (os .getenv (name )or "").strip ()
    try :
        return int (raw )if raw else int (default )
    except Exception :
        return int (default )


BOT_TOKEN =os .getenv ("BOT_TOKEN")
AI_API_KEY =os .getenv ("OPENROUTER_API_KEY")or os .getenv ("AI_API_KEY")
ADMIN_CHAT_ID =os .getenv ("ADMIN_CHAT_ID")# optional
TG_PRIVATE_CHANNEL_INVITE_LINK =os .getenv ("TG_PRIVATE_CHANNEL_INVITE_LINK")
CRM_API_BASE_URL =(os .getenv ("CRM_API_BASE_URL")or "http://web:8000").rstrip ("/")
CRM_API_TOKEN =(os .getenv ("CRM_API_TOKEN")or "").strip ()
BOT_API_TOKEN =(os .getenv ("BOT_API_TOKEN")or "").strip ()
YOOMONEY_PAY_URL_PLACEHOLDER =(os .getenv ("YOOMONEY_PAY_URL_PLACEHOLDER")or "").strip ()
TELEGRAM_PRIVATE_CHANNEL_ID =(os .getenv ("TELEGRAM_PRIVATE_CHANNEL_ID")or "").strip ()
PAYMENTS_TEST_ENABLED =_env_flag_enabled_default_false ("PAYMENTS_TEST_ENABLED")
PAYMENTS_TEST_AMOUNT_RUB =max (1 ,_int_env ("PAYMENTS_TEST_AMOUNT_RUB",10 ))
BOT_ADMIN_ID_SET =set ()

# ADMIN_CHAT_ID is kept for backward compatibility; BOT_ADMIN_IDS is preferred.
BOT_ADMIN_ID_SET =_parse_admin_ids ()

# Services
ai_service =AIService (api_key =AI_API_KEY )
logger .info ("AI configured: key=%s model=%s",bool (AI_API_KEY ),ai_service .model )
screen_manager =ScreenManager ()


# In-memory (history can be moved to Redis/DB if needed)
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
PENDING_EVENT_ACTIONS_KEY ="pending_event_actions"
SKIP_NEXT_EMAIL_KEY ="skip_next_email"
PAYMENT_CONTACT_FLOW_KEY ="payment_contact_flow"
PAYMENT_PENDING_ACTION_KEY ="payment_pending_action"
PAYMENT_CONTACT_MODE_KEY ="payment_contact_mode"
PAYMENT_VARIANT_KEY ="payment_variant"
LAST_GAME10_PAYMENT_UI_KEY ="last_game10_payment_ui"
PRODUCT_FOCUS_KEY ="product_focus"
LAST_USER_ACTIVITY_TS_KEY ="last_user_activity_ts"
LOCK_FILE_PATH =get_lock_path ()
_BOT_LOCK_FD =None 
LOCK_HEARTBEAT_SECONDS =30 
PRODUCT_FOCUS_TIMEOUT_SEC =30 *60
USER_BUSY_IDS :set [int ]=set ()
BUSY_NOTICE_TS_KEY ="busy_notice_ts"
BUSY_NOTICE_INTERVAL_SEC =4.0

EMAIL_RE =re .compile (r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
COURSES_PAGE_SIZE =5 
EVENTS_LIST_PAGE_SIZE =6
EVENTS_CACHE_KEY ="events_cache"
EVENTS_LIST_PAGE_KEY ="events_list_page"
SCREEN_KIND_KEY ="screen_kind"
SCREEN_EVENT_ID_KEY ="screen_event_id"
AUTO_AI_REPLY_TIMESTAMPS_KEY ="auto_ai_reply_timestamps"
AUTO_AI_RATE_LIMIT_WINDOW_SEC =12
AUTO_AI_RATE_LIMIT_MAX =3

PAYMENT_CREATING_SCREEN ="Создаю оплату..."
PAYMENT_NEED_CONTACT_SCREEN ="Для оплаты нужен телефон или email (для отправки чека). Выберите вариант."
PAYMENT_ASK_PHONE_SCREEN ="Поделитесь номером телефона.\nЭто нужно для отправки чека."
PAYMENT_ASK_EMAIL_SCREEN ="Напишите email одним сообщением.\nЭто нужно для отправки чека."
PAYMENT_CONTACT_SAVED_SCREEN ="Контакт получен. Формирую оплату..."
PAYMENT_CANCELLED_SCREEN ="Ок. Оплату отменил."
PAYMENT_LINK_READY_SCREEN ="Ссылка на оплату готова.\nОткройте оплату или отсканируйте QR."
PAYMENT_EXPIRED_HINT ="Ссылка устарела. Создаю новую..."
PAYMENT_CHECKING_SCREEN ="Проверяю оплату..."
PAYMENT_STATUS_PENDING_SCREEN ="Оплата пока не подтверждена. Попробуйте позже."
PAYMENT_STATUS_CANCELED_SCREEN ="Платеж отменен или истек. Нажмите «Обновить ссылку»."
PAYMENT_STATUS_CONFIRMED_SCREEN ="Оплата подтверждена. Нажмите «Вступить в канал»."
PAYMENT_ALREADY_IN_CHANNEL_SCREEN ="Вы уже состоите в закрытом канале."
PAYMENT_VARIANT_MAIN ="game10_main"
ASSISTANT_ENTRY_HINT_TEXT ="Чтобы задать вопрос ассистенту, откройте раздел и нажмите «Вопросы к ассистенту»."


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
    if "reply_markup" in kwargs :
        kwargs ["reply_markup"]=normalize_ui_reply_markup (kwargs .get ("reply_markup"))
    return await message .reply_text (_t (text ,label ="reply")or "",**kwargs )


async def _edit (query :CallbackQuery |None ,text :str |None ,**kwargs ):
    if query is None :
        return None 
    if "reply_markup" in kwargs :
        kwargs ["reply_markup"]=normalize_ui_reply_markup (kwargs .get ("reply_markup"))
    return await query .edit_message_text (_t (text ,label ="edit")or "",**kwargs )


async def _send (bot ,chat_id :int ,text :str |None =None ,**kwargs ):
    payload =text if text is not None else kwargs .pop ("text",None )
    if "reply_markup" in kwargs :
        kwargs ["reply_markup"]=normalize_ui_reply_markup (kwargs .get ("reply_markup"))
    return await bot .send_message (chat_id =chat_id ,text =_t (payload ,label ="send")or "",**kwargs )


async def _send_photo (bot ,chat_id :int ,photo ,caption :str |None =None ,**kwargs ):
    if "reply_markup" in kwargs :
        kwargs ["reply_markup"]=normalize_ui_reply_markup (kwargs .get ("reply_markup"))
    return await bot .send_photo (
    chat_id =chat_id ,
    photo =photo ,
    caption =_t (caption ,label ="send_photo")or None ,
    **kwargs ,
    )


async def _show_screen (update :Update ,context :ContextTypes .DEFAULT_TYPE ,text :str |None ,**kwargs ):
    _apply_focus_timeout (context )
    return await screen_manager .show_screen (update ,context ,text ,**kwargs )


async def _show_main_menu_bottom (update :Update ,context :ContextTypes .DEFAULT_TYPE ,text :str |None =None ):
    if text is None :
        text ="Главное меню"
    screen_manager .clear_screen (context )
    await _show_screen (update ,context ,text ,reply_markup =get_main_menu ())


async def _safe_edit_reply_markup (query :CallbackQuery |None ,*,reply_markup =None ):
    if query is None :
        return None
    reply_markup =normalize_ui_reply_markup (reply_markup )
    try :
        return await query .edit_message_reply_markup (reply_markup =reply_markup )
    except BadRequest as e :
        message =(str (e )or "").lower ()
        if "message is not modified" in message :
            return None
        raise


def _bot_api_auth_headers ()->dict [str ,str ]:
    token =(BOT_API_TOKEN or "").strip ()
    if not token :
        return {}
    return {"X-Bot-Api-Token":token }


def _clear_payment_contact_flow (context :ContextTypes .DEFAULT_TYPE )->None :
    context .user_data .pop (PAYMENT_CONTACT_FLOW_KEY ,None )
    context .user_data .pop (PAYMENT_PENDING_ACTION_KEY ,None )
    context .user_data .pop (PAYMENT_CONTACT_MODE_KEY ,None )
    context .user_data .pop (PAYMENT_VARIANT_KEY ,None )


def _clear_payment_runtime_state (context :ContextTypes .DEFAULT_TYPE )->None :
    _clear_payment_contact_flow (context )
    context .user_data .pop ("last_payment_id",None )
    context .user_data .pop (LAST_GAME10_PAYMENT_UI_KEY ,None )


def _start_payment_contact_flow_state (context :ContextTypes .DEFAULT_TYPE ,*,variant :str )->None :
    context .user_data [PAYMENT_CONTACT_FLOW_KEY ]=True
    context .user_data [PAYMENT_PENDING_ACTION_KEY ]="game10_payment"
    context .user_data [PAYMENT_VARIANT_KEY ]=variant
    context .user_data .pop (PAYMENT_CONTACT_MODE_KEY ,None )


def _payment_variant_normalized (variant :str |None )->str :
    _ =variant
    return PAYMENT_VARIANT_MAIN


def _payment_variant_amount_rub (variant :str |None )->int :
    _ =variant
    return 5000


def _payment_variant_refresh_callback (variant :str |None )->str :
    _ =variant
    return "game10_pay_refresh"


def _payment_variant_endpoint_path (variant :str |None )->str :
    _ =variant
    return "/api/payments/game10/create"


def _is_admin_user_id (user_id :int |None )->bool :
    if user_id is None :
        return False
    return int (user_id )in BOT_ADMIN_ID_SET


def _game10_kb_for_update (update :Update )->InlineKeyboardMarkup :
    _ =update
    return get_game10_kb (_private_channel_payment_url ())


def _payment_check_callback_data (payment_id :str )->str |None :
    value =str (payment_id or "").strip ()
    if not value :
        return None
    callback =f"pay_check:{value }"
    if len (callback )>64:
        return None
    return callback


def _payment_return_kb (payment_id :str |None )->InlineKeyboardMarkup :
    check_callback =_payment_check_callback_data (str (payment_id or "").strip ())or "pay_check:"
    return InlineKeyboardMarkup ([
    [InlineKeyboardButton ("\u2705 \u042f \u043e\u043f\u043b\u0430\u0442\u0438\u043b \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",callback_data =check_callback )],
    [InlineKeyboardButton ("\u21a9\ufe0f \u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
    ])


def _store_last_game10_payment_ui_state (context :ContextTypes .DEFAULT_TYPE ,*,payment_id :str ,confirmation_url :str ,variant :str ,message_id :int |None =None )->None :
    context .user_data [LAST_GAME10_PAYMENT_UI_KEY ]={
    "payment_id":str (payment_id or ""),
    "confirmation_url":str (confirmation_url or ""),
    "variant":_payment_variant_normalized (variant ),
    "message_id":int (message_id )if message_id is not None else None,
    }


async def _delete_last_game10_payment_ui_message (update :Update ,context :ContextTypes .DEFAULT_TYPE )->None :
    chat =update .effective_chat
    if chat is None :
        return
    data =context .user_data .get (LAST_GAME10_PAYMENT_UI_KEY )
    if not isinstance (data ,dict ):
        return
    message_id =data .get ("message_id")
    if not message_id :
        return
    try :
        await context .bot .delete_message (chat_id =chat .id ,message_id =int (message_id ))
    except Exception :
        pass


def _get_last_game10_payment_ui_kb (context :ContextTypes .DEFAULT_TYPE ,payment_id :str |None )->InlineKeyboardMarkup |None :
    data =context .user_data .get (LAST_GAME10_PAYMENT_UI_KEY )
    if not isinstance (data ,dict ):
        return None
    saved_payment_id =str (data .get ("payment_id")or "").strip ()
    if payment_id and saved_payment_id and saved_payment_id !=str (payment_id ).strip ():
        return None
    confirmation_url =str (data .get ("confirmation_url")or "").strip ()
    if not confirmation_url :
        return None
    variant =_payment_variant_normalized (str (data .get ("variant")or ""))
    return get_game10_payment_link_kb (
    confirmation_url ,
    refresh_callback_data =_payment_variant_refresh_callback (variant ),
    check_callback_data =_payment_check_callback_data (saved_payment_id ),
    )


def _payment_backend_need_contact (result :dict |None )->bool :
    if not isinstance (result ,dict ):
        return False
    if int (result .get ("status_code")or 0 )!=400:
        return False
    detail =str (result .get ("detail")or "").lower ()
    return ("email" in detail and "телефон" in detail )or ("phone" in detail and "email" in detail)or ("receipt" in detail and "email" in detail)

async def _create_game10_payment_backend (tg_id :int ,*,variant :str =PAYMENT_VARIANT_MAIN )->dict |None :
    if not CRM_API_BASE_URL :
        return None
    headers =_bot_api_auth_headers ()
    if not headers :
        logger .warning ("Game10 payment backend token missing")
        return None
    try :
        async with httpx .AsyncClient (timeout =20.0 )as client :
            response =await client .post (
            f"{CRM_API_BASE_URL }{_payment_variant_endpoint_path (variant )}",
            headers =headers ,
            json ={"tg_id":int (tg_id )},
            )
        if response .status_code !=200 :
            detail =response .text [:240 ]
            try :
                payload =response .json ()
                if isinstance (payload ,dict )and payload .get ("detail")is not None :
                    detail =str (payload .get ("detail"))
            except Exception :
                pass
            return {"ok":False ,"status_code":response .status_code ,"detail":detail [:240 ]}
        payload =response .json ()
        if not isinstance (payload ,dict ):
            return {"ok":False ,"detail":"invalid backend payload"}
        payload ["ok"]=True
        return payload
    except Exception as e :
        logger .warning ("Game10 payment create request failed: %s",e .__class__ .__name__ )
        return {"ok":False ,"detail":e .__class__ .__name__ }


async def _create_test_payment_backend (tg_id :int )->dict |None :
    if not CRM_API_BASE_URL :
        return None
    headers =_bot_api_auth_headers ()
    if not headers :
        logger .warning ("Test payment backend token missing")
        return None
    payload ={
    "tg_id":int (tg_id ),
    "product":"game10_test",
    "amount_rub":int (PAYMENTS_TEST_AMOUNT_RUB ),
    }
    try :
        async with httpx .AsyncClient (timeout =20.0 )as client :
            response =await client .post (
            f"{CRM_API_BASE_URL }/api/payments/test/create",
            headers =headers ,
            json =payload ,
            )
        if response .status_code !=200 :
            detail =response .text [:240 ]
            try :
                payload =response .json ()
                if isinstance (payload ,dict )and payload .get ("detail")is not None :
                    detail =str (payload .get ("detail"))
            except Exception :
                pass
            return {"ok":False ,"status_code":response .status_code ,"detail":detail [:240 ]}
        payload =response .json ()
        if not isinstance (payload ,dict ):
            return {"ok":False ,"detail":"invalid backend payload"}
        payload ["ok"]=True
        return payload
    except Exception as e :
        logger .warning ("Test payment create request failed: %s",e .__class__ .__name__ )
        return {"ok":False ,"detail":e .__class__ .__name__ }


async def _check_game10_payment_status_backend (payment_id :str ,*,tg_id :int |None =None )->dict |None :
    payment_id =str (payment_id or "").strip ()
    if not payment_id or not CRM_API_BASE_URL :
        return None
    headers =_bot_api_auth_headers ()
    if not headers :
        logger .warning ("Game10 payment status backend token missing")
        return None
    try :
        async with httpx .AsyncClient (timeout =20.0 )as client :
            response =await client .post (
            f"{CRM_API_BASE_URL }/api/payments/yookassa/status",
            headers =headers ,
            json ={"payment_id":payment_id ,"tg_id":int (tg_id )}if tg_id else {"payment_id":payment_id },
            )
        if response .status_code !=200:
            detail =response .text [:240 ]
            try :
                payload =response .json ()
                if isinstance (payload ,dict )and payload .get ("detail")is not None :
                    detail =str (payload .get ("detail"))
            except Exception :
                pass
            return {"ok":False ,"status_code":response .status_code ,"detail":detail [:240 ]}
        payload =response .json ()
        if not isinstance (payload ,dict ):
            return {"ok":False ,"detail":"invalid backend payload"}
        payload ["ok"]=True
        return payload
    except Exception as e :
        logger .warning ("Game10 payment status request failed: %s",e .__class__ .__name__ )
        return {"ok":False ,"detail":e .__class__ .__name__ }


async def _send_reply_keyboard_remove (update :Update ,context :ContextTypes .DEFAULT_TYPE )->None :
    chat =update .effective_chat
    if chat is None :
        return
    try :
        await _send (context .bot ,chat_id =chat .id ,text ="\u200b",reply_markup =get_remove_reply_kb ())
    except Exception :
        return


async def _send_game10_payment_qr_and_screen (
update :Update ,
context :ContextTypes .DEFAULT_TYPE ,
*,
confirmation_url :str ,
payment_id :str ,
amount_rub :int ,
variant :str =PAYMENT_VARIANT_MAIN ,
)->None :
    chat =update .effective_chat
    if chat is None :
        return
    pay_kb =get_game10_payment_link_kb (
    confirmation_url ,
    refresh_callback_data =_payment_variant_refresh_callback (variant ),
    check_callback_data =_payment_check_callback_data (payment_id ),
    )
    caption =(
    f"\u041e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 {amount_rub} \u20bd. \u041f\u043e\u0441\u043b\u0435 \u043e\u043f\u043b\u0430\u0442\u044b \u0434\u043e\u0441\u0442\u0443\u043f \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.\n"
    "\u041f\u043e\u0441\u043b\u0435 \u043e\u043f\u043b\u0430\u0442\u044b \u0431\u043e\u0442 \u043f\u0440\u0438\u0448\u043b\u0435\u0442 \u043a\u043d\u043e\u043f\u043a\u0443 \u0434\u043b\u044f \u0432\u0441\u0442\u0443\u043f\u043b\u0435\u043d\u0438\u044f \u0432 \u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u043a\u0430\u043d\u0430\u043b."
    )
    await _delete_last_game10_payment_ui_message (update ,context )
    qr =_build_qr_png (confirmation_url )
    if qr is not None :
        sent =await _send_photo (context .bot ,chat .id ,qr ,caption =caption ,reply_markup =pay_kb )
    else :
        sent =await _send (context .bot ,chat_id =chat .id ,text =caption ,reply_markup =pay_kb )
    _store_last_game10_payment_ui_state (
    context ,
    payment_id =payment_id ,
    confirmation_url =confirmation_url ,
    variant =variant ,
    message_id =getattr (sent ,"message_id",None ),
    )


async def _request_payment_contact_screen (update :Update ,context :ContextTypes .DEFAULT_TYPE ,*,variant :str )->None :
    _start_payment_contact_flow_state (context ,variant =_payment_variant_normalized (variant ))
    await _show_screen (
    update ,
    context ,
    PAYMENT_NEED_CONTACT_SCREEN ,
    reply_markup =get_payment_contact_choice_kb (),
    )


async def _run_game10_payment_create_flow (
update :Update ,
context :ContextTypes .DEFAULT_TYPE ,
*,
variant :str |None =None ,
refresh_hint :bool =False ,
)->None :
    user =update .effective_user
    if user is None :
        return
    payment_variant =_payment_variant_normalized (variant or context .user_data .get (PAYMENT_VARIANT_KEY ))
    context .user_data [PAYMENT_VARIANT_KEY ]=payment_variant
    await _show_screen (
    update ,
    context ,
    PAYMENT_EXPIRED_HINT if refresh_hint else PAYMENT_CREATING_SCREEN ,
    reply_markup =_game10_kb_for_update (update ),
    )
    result =await _create_game10_payment_backend (user .id ,variant =payment_variant )
    if not isinstance (result ,dict )or not result .get ("ok"):
        if _payment_backend_need_contact (result ):
            await _request_payment_contact_screen (update ,context ,variant =payment_variant )
            return
        _clear_payment_contact_flow (context )
        await _show_screen (
        update ,
        context ,
        "Сейчас не удалось создать платёж. Попробуйте ещё раз через минуту или нажмите «Связаться с менеджером».",
        reply_markup =_game10_kb_for_update (update ),
        )
        return
    _clear_payment_contact_flow (context )
    confirmation_url =str (result .get ("confirmation_url")or "").strip ()
    payment_id =str (result .get ("payment_id")or "").strip ()
    context .user_data ["last_payment_id"]=payment_id
    amount_rub =int (result .get ("amount_rub")or 5000 )
    if not confirmation_url :
        _clear_payment_contact_flow (context )
        await _show_screen (
        update ,
        context ,
        "Платёж создан, но ссылка оплаты не получена. Нажмите «Связаться с менеджером».",
        reply_markup =_game10_kb_for_update (update ),
        )
        return
    await _send_game10_payment_qr_and_screen (
    update ,
    context ,
    confirmation_url =confirmation_url ,
    payment_id =payment_id ,
    amount_rub =amount_rub ,
    variant =payment_variant ,
    )


def _build_qr_png (value :str )->BytesIO |None :
    if not value :
        return None
    if qrcode is None :
        return None
    try :
        img =qrcode .make (value )
        buf =BytesIO ()
        img .save (buf ,format ="PNG")
        buf .seek (0 )
        buf .name ="game10_payment_qr.png"
        return buf
    except Exception as e :
        logger .warning ("QR generation failed: %s",e .__class__ .__name__ )
        return None


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


async def _is_private_channel_paid_local (tg_id :int )->bool :
    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            result =await crm_service .is_private_channel_paid (tg_id )
            await session .commit ()
            return bool (result )
    except Exception as e :
        logger .warning ("Private channel paid check failed: %s",e .__class__ .__name__ )
        return False


async def _get_last_game10_payment_local (tg_id :int )->dict |None :
    try :
        db .init_db ()
        async with db .async_session ()as session :
            row =await session .execute (
            select (YooKassaPayment )
            .where (YooKassaPayment .tg_id ==tg_id )
            .where (YooKassaPayment .product =="game10")
            .order_by (YooKassaPayment .created_at .desc ())
            .limit (1 )
            )
            item =row .scalar_one_or_none ()
            user_row =await session .execute (
            select (User .email ,User .phone )
            .where (User .tg_id ==tg_id )
            .limit (1 )
            )
            user_map =user_row .mappings ().first ()
            await session .commit ()
            if item is None :
                return None
            return {
            "payment_id":str (item .payment_id or ""),
            "product":str (item .product or ""),
            "status":str (item .status or ""),
            "created_at":item .created_at ,
            "paid_at":item .paid_at ,
            "has_email":bool ((user_map or {}).get ("email")),
            "has_phone":bool ((user_map or {}).get ("phone")),
            }
    except Exception as e :
        logger .warning ("Game10 payment debug lookup failed: %s",e .__class__ .__name__ )
        return None


def _short_text (value :str |None ,limit :int =420 )->str :
    if not value :
        return "Описание не указано."
    text =normalize_text_for_telegram (value )or value 
    if len (text )<=limit :
        return text 
    return text [:limit ].rstrip ()+"..."


def _format_catalog_price (price_value )->str :
    try :
        if price_value is None :
            return "Цена по запросу"
        price =int (float (price_value ))
        if price <=0 :
            return "Бесплатно"
        return f"{price } \u20bd"
    except Exception :
        return "Цена по запросу"


def _format_catalog_item_card (item :CatalogItem )->str :
    title =normalize_text_for_telegram (item .title )or "Без названия"
    description =_short_text (item .description )
    price_text =_format_catalog_price (item .price )
    return (
    f"{title }\n"
    f"\u0426\u0435\u043d\u0430: {price_text }\n\n"
    f"{description }"
    )

GESTALT_SHORT_SCREEN_1 =(
"*\u0413\u0435\u0448\u0442\u0430\u043b\u044c\u0442-\u0442\u0435\u0440\u0430\u043f\u0438\u044f*\n\n"
"\u041f\u043e\u043c\u043e\u0433\u0430\u0435\u0442:\n"
"- \u043b\u0443\u0447\u0448\u0435 \u043f\u043e\u043d\u0438\u043c\u0430\u0442\u044c \u0441\u0432\u043e\u0438 \u0447\u0443\u0432\u0441\u0442\u0432\u0430\n"
"- \u0441\u043d\u0438\u0436\u0430\u0442\u044c \u0432\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0435\u0435 \u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u0435\n"
"- \u0436\u0438\u0442\u044c \u043e\u0441\u043e\u0437\u043d\u0430\u043d\u043d\u043e."
)

GESTALT_SHORT_SCREEN_2 =(
"*\u0424\u043e\u0440\u043c\u0430\u0442\u044b \u0438 \u0446\u0435\u043d\u044b*\n\n"
"*\u0418\u043d\u0434\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d\u0430\u044f \u0442\u0435\u0440\u0430\u043f\u0438\u044f*\n"
"\u041b\u0438\u0447\u043d\u043e\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u0434\u043b\u044f \u0440\u0430\u0431\u043e\u0442\u044b \u0441 \u0441\u043e\u0431\u043e\u0439.\n"
"\u0426\u0435\u043d\u0430: *\u0443\u0442\u043e\u0447\u043d\u044f\u0435\u0442\u0441\u044f \u043f\u0440\u0438 \u0437\u0430\u043f\u0438\u0441\u0438*\n\n"
"*\u0413\u0440\u0443\u043f\u043f\u043e\u0432\u0430\u044f \u0442\u0435\u0440\u0430\u043f\u0438\u044f*\n"
"\u0411\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u0430\u044f \u0433\u0440\u0443\u043f\u043f\u0430 \u0434\u043b\u044f \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0438 \u0438 \u043e\u043f\u044b\u0442\u0430.\n"
"\u0426\u0435\u043d\u0430: *\u0443\u0442\u043e\u0447\u043d\u044f\u0435\u0442\u0441\u044f \u043f\u0440\u0438 \u0437\u0430\u043f\u0438\u0441\u0438*."
)

ASSISTANT_GREETING =(
"\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435, \u044f \u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0420\u0435\u043d\u0430\u0442\u044b \u041c\u0438\u043d\u0430\u043a\u043e\u0432\u043e\u0439. \u041a\u0430\u043a\u043e\u0439 \u0443 \u0432\u0430\u0441 \u0432\u043e\u043f\u0440\u043e\u0441?"
)

COURSE_ASSISTANT_GREETING =(
"\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435, \u044f \u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0420\u0435\u043d\u0430\u0442\u044b \u041c\u0438\u043d\u0430\u043a\u043e\u0432\u043e\u0439. \u0417\u0430\u0434\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043e \u043a\u0443\u0440\u0441\u0435, \u044f \u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0443 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0443, \u043a\u043e\u043c\u0443 \u043f\u043e\u0434\u043e\u0439\u0434\u0435\u0442 \u0438 \u043a\u0430\u043a \u0437\u0430\u043f\u0438\u0441\u0430\u0442\u044c\u0441\u044f.\n\n"
"\u041f\u0440\u0438\u043c\u0435\u0440\u044b \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432:\n"
"- \u041a\u0430\u043a\u0430\u044f \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u043a\u0443\u0440\u0441\u0430?\n"
"- \u041a\u043e\u043c\u0443 \u043f\u043e\u0434\u043e\u0439\u0434\u0435\u0442 \u043a\u0443\u0440\u0441 \u0438 \u043a\u0430\u043a \u0437\u0430\u043f\u0438\u0441\u0430\u0442\u044c\u0441\u044f?"
)

ONLINE_COURSES_TEXT =(
"\u0410\u0432\u0442\u043e\u0440\u0441\u043a\u0438\u0439 \u043a\u0443\u0440\u0441 \u043b\u0435\u043a\u0446\u0438\u0439 \u043e \u043b\u0438\u0447\u043d\u043e\u043c \u0440\u043e\u0441\u0442\u0435 \u0438 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u044f\u0445 \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f.\n\n"
"\u0412\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0435 \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u0443\u044e \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0443 \u0438 \u043f\u0440\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u044b."
)

GAME10_SCREEN_TEXT =(
"\u00ab\u0418\u0433\u0440\u0430 10:0\u00bb\n\n"
"\u0422\u044b \u0432 \u0437\u0430\u043a\u0440\u044b\u0442\u043e\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u0435 \u00ab\u0418\u0433\u0440\u0430 10:0\u00bb. \u0417\u0434\u0435\u0441\u044c \u0442\u044b \u043d\u0430\u0447\u043d\u0435\u0448\u044c \u0434\u0435\u0439\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c \u0438 \u043f\u043e\u0431\u0435\u0436\u0434\u0430\u0442\u044c. "
"\u0422\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0448\u044c \u0440\u0430\u0441\u043f\u0430\u043a\u043e\u0432\u043a\u0443 \u0441\u0432\u043e\u0435\u0439 \u0441\u0443\u043f\u0435\u0440-\u0441\u0438\u043b\u044b \u0432 \u043e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u044f\u0445, \u043a\u0430\u0440\u044c\u0435\u0440\u0435, \u0431\u0438\u0437\u043d\u0435\u0441\u0435 \u0438 \u0437\u0434\u043e\u0440\u043e\u0432\u044c\u0435. "
"\u042d\u0442\u043e \u0431\u0435\u0440\u0435\u0436\u043d\u0430\u044f \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433\u0438\u044f, \u0441\u043e\u0431\u0440\u0430\u043d\u043d\u0430\u044f \u0438\u0437 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u043e\u0439 \u043f\u0441\u0438\u0445\u043e\u043b\u043e\u0433\u0438\u0438 \u0438 \u043d\u0435\u0439\u0440\u043e\u043f\u0440\u0430\u043a\u0442\u0438\u043a."
)

GAME10_ASSISTANT_GREETING =(
"\u0417\u0430\u0434\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441 \u043f\u0440\u043e \u00ab\u0418\u0433\u0440\u0430 10:0\u00bb.\n"
"\u041d\u0430\u043f\u0440\u0438\u043c\u0435\u0440:\n"
"- \u0421 \u0447\u0435\u0433\u043e \u043d\u0430\u0447\u0430\u0442\u044c \u0432 \u00ab\u0418\u0433\u0440\u0430 10:0\u00bb?\n"
"- \u0427\u0442\u043e \u044f \u043f\u043e\u043b\u0443\u0447\u0443 \u0432 \u0441\u043e\u043e\u0431\u0449\u0435\u0441\u0442\u0432\u0435?\n"
"- \u041a\u0430\u043a \u043f\u0440\u043e\u0445\u043e\u0434\u0438\u0442 \u0440\u0430\u0431\u043e\u0442\u0430 \u0438 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430?"
)


GAME10_DESCRIPTION_SCREEN_TEXT ="""\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u044b

\u0424\u043e\u0440\u043c\u0430\u0442 \u0440\u0430\u0431\u043e\u0442\u044b: 4 \u043d\u0435\u0434\u0435\u043b\u0438, 4 \u0442\u0435\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u0431\u043b\u043e\u043a\u0430. \u041e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u044f, \u0434\u0435\u043d\u044c\u0433\u0438, \u044d\u043d\u0435\u0440\u0433\u0438\u044f, \u0442\u0430\u043b\u0430\u043d\u0442\u044b.

\u0427\u0442\u043e \u0432\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0435:
- \u041f\u043e\u043d\u044f\u0442\u043d\u044b\u0435 \u0437\u043d\u0430\u043d\u0438\u044f \u043f\u043e \u044d\u0442\u0438\u043c \u0442\u0435\u043c\u0430\u043c, \u0442\u043e\u043b\u044c\u043a\u043e \u0442\u043e, \u0447\u0442\u043e \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442
- \u0427\u0435\u0442\u043a\u0438\u0435 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438, \u043a\u0430\u043a \u043d\u0430\u043b\u0430\u0434\u0438\u0442\u044c \u0436\u0438\u0437\u043d\u044c \u0432 \u044d\u0442\u0438\u0445 \u0441\u0444\u0435\u0440\u0430\u0445
- \u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u043e\u0441\u0442\u0430\u043d\u0443\u0442\u0441\u044f \u0441 \u0432\u0430\u043c\u0438
- \u0414\u043b\u044f \u043f\u0441\u0438\u0445\u043e\u043b\u043e\u0433\u043e\u0432: \u043d\u043e\u0432\u044b\u0435 \u0440\u0430\u0431\u043e\u0447\u0438\u0435 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u044b

\u041a\u0442\u043e \u0432\u0435\u0434\u0435\u0442: \u0420\u0435\u043d\u0430\u0442\u0430 \u041c\u0438\u043d\u0430\u043a\u043e\u0432\u0430 \u0438 \u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0434\u0438\u043f\u043b\u043e\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0445 \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u043e\u0432.
"""


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
    _clear_payment_contact_flow (context )
    context .user_data .pop ("last_payment_id",None )
    context .user_data .pop (LAST_GAME10_PAYMENT_UI_KEY ,None )
    context .user_data .pop (BUSY_NOTICE_TS_KEY ,None )
    context .user_data .pop (PRODUCT_FOCUS_KEY ,None )


def _apply_focus_timeout (context :ContextTypes .DEFAULT_TYPE )->bool :
    return apply_focus_timeout_state (
    context .user_data ,
    now_ts =time .time (),
    timeout_sec =PRODUCT_FOCUS_TIMEOUT_SEC ,
    focus_key =PRODUCT_FOCUS_KEY ,
    last_activity_key =LAST_USER_ACTIVITY_TS_KEY ,
    )


def _clear_product_focus (context :ContextTypes .DEFAULT_TYPE )->None :
    context .user_data .pop (PRODUCT_FOCUS_KEY ,None )


def _is_db_exception (exc :Exception |None )->bool :
    if exc is None :
        return False
    cls =exc .__class__
    module_name =str (getattr (cls ,"__module__", "")or "").lower ()
    class_name =str (getattr (cls ,"__name__", "")or "").lower ()
    if "sqlalchemy" in module_name or "asyncpg" in module_name or "psycopg" in module_name :
        return True
    markers =("database","dbapi","operationalerror","interfaceerror","connectionerror","pooltimeout","timeouterror")
    return any (marker in class_name for marker in markers )


def _update_kind (update :Update )->str :
    if getattr (update ,"callback_query",None )is not None :
        return "callback"
    if getattr (update ,"message",None )is not None :
        return "message"
    if getattr (update ,"chat_join_request",None )is not None :
        return "chat_join_request"
    return "other"


def _log_action_duration (action :str ,started_at :float ,update :Update )->None :
    duration_ms =round ((time .perf_counter ()-started_at )*1000 ,2 )
    logger .info (
    "bot_action duration_ms=%s action=%s update_kind=%s",
    duration_ms ,
    action ,
    _update_kind (update ),
    )


def _try_enter_user_busy (user_id :int )->bool :
    if user_id in USER_BUSY_IDS :
        return False
    USER_BUSY_IDS .add (user_id )
    return True


def _leave_user_busy (user_id :int )->None :
    USER_BUSY_IDS .discard (user_id )


async def _handle_busy_update (update :Update ,context :ContextTypes .DEFAULT_TYPE ,*,busy_mode :str )->None :
    query =getattr (update ,"callback_query",None )
    if query is not None :
        try :
            if busy_mode =="notify":
                await _answer (query ,"\u042f \u043e\u0442\u0432\u0435\u0447\u0430\u044e, \u043f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435.")
            else :
                await _answer (query )
        except Exception :
            pass
        return
    if busy_mode !="notify":
        return
    message =getattr (update ,"effective_message",None )
    if message is None :
        return
    now_ts =time .time ()
    last_notice =float (context .user_data .get (BUSY_NOTICE_TS_KEY )or 0.0 )
    if now_ts -last_notice <BUSY_NOTICE_INTERVAL_SEC :
        return
    context .user_data [BUSY_NOTICE_TS_KEY ]=now_ts
    try :
        await _reply (message ,"\u042f \u043e\u0442\u0432\u0435\u0447\u0430\u044e, \u043f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435.")
    except Exception :
        pass


def _guard_user_handler (handler ,*,action :str |None =None ,busy_mode :str ="notify"):
    async def _wrapped (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
        tg_user =getattr (update ,"effective_user",None )
        user_id =int (tg_user .id )if tg_user is not None else None
        if user_id is not None and not _try_enter_user_busy (user_id ):
            await _handle_busy_update (update ,context ,busy_mode =busy_mode )
            raise ApplicationHandlerStop
        started_at =time .perf_counter ()
        try :
            return await handler (update ,context )
        finally :
            if user_id is not None :
                _leave_user_busy (user_id )
            _log_action_duration (action or getattr (handler ,"__name__","handler"),started_at ,update )
    _wrapped .__name__ =getattr (handler ,"__name__","guarded_handler")
    return _wrapped


def _err_name (exc :Exception |None )->str :
    return exc .__class__ .__name__ if exc is not None else "UnknownError"


def _err_short (exc :Exception |None ,limit :int =180 )->str :
    if exc is None :
        return ""
    text =str (exc ).replace ("\r"," ").replace ("\n"," ").strip ()
    text =re .sub (r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^\\s@]+@","\\1***@",text )
    text =re .sub (r"(password\\s*[=:]\\s*)([^\\s,;]+)",r"\\1***",text ,flags =re .IGNORECASE )
    text =re .sub (r"(pwd\\s*[=:]\\s*)([^\\s,;]+)",r"\\1***",text ,flags =re .IGNORECASE )
    text =re .sub (r"(token\\s*[=:]\\s*)([^\\s,;]+)",r"\\1***",text ,flags =re .IGNORECASE )
    if len (text )>limit :
        text =text [:limit ]+"..."
    return text


def _log_db_issue (scope :str ,exc :Exception |None =None )->None :
    short =_err_short (exc )
    if short :
        logger .warning ("DB issue [%s]: %s: %s",scope ,_err_name (exc ),short )
    else :
        logger .warning ("DB issue [%s]: %s",scope ,_err_name (exc ))



def _remember_pending_event_action (context :ContextTypes .DEFAULT_TYPE ,update :Update ,*,action :str ,event_id :int )->None :
    pending =list (context .user_data .get (PENDING_EVENT_ACTIONS_KEY )or [])
    tg_user =update .effective_user
    payload ={
    "action":str (action ),
    "event_id":int (event_id ),
    "updated_at":datetime .utcnow ().isoformat (),
    }
    if tg_user is not None :
        payload ["tg_id"]=int (tg_user .id )
    pending .append (payload )
    context .user_data [PENDING_EVENT_ACTIONS_KEY ]=pending [-10 :]

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



def classify_update_need_db (update :Update ,context :ContextTypes .DEFAULT_TYPE |None =None )->bool :
    message =getattr (update ,"effective_message",None )
    callback =getattr (update ,"callback_query",None )
    callback_data =str (getattr (callback ,"data",None )or "")

    if callback_data :
        nav_prefixes =(
        "main_menu",
        "menu",
        "events",
        "events_list",
        "event_open:",
        "event_list_prev",
        "event_list_next",
        "event_list_refresh",
        "courses",
        "courses_page:",
        "private_channel",
        "game10_questions",
        "consultations",
        "consult_formats",
        "ai_chat",
        "course_questions",
        "share_contacts",
        "contact_manager",
        "help",
        "retry_db",
        )
        if any (callback_data .startswith (prefix )for prefix in nav_prefixes ):
            return False
        if any (callback_data .startswith (prefix )for prefix in ("event_register:","event_cancel:","event_pay:")):
            return True

    if message is None :
        return False
    text_value =str (getattr (message ,"text",None )or "").strip ()
    if text_value .startswith ("/"):
        command =text_value .split ()[0 ].lower ()
        if command in {"/start","/menu","/back","/cancel","/events","/courses","/catalog"}:
            return False
    if context is not None and (
    context .user_data .get (WAITING_CONTACT_PHONE_KEY )
    or context .user_data .get (WAITING_CONTACT_EMAIL_KEY )
    or context .user_data .get (CONTACT_FLOW_KEY )
    ):
        return True
    return False

async def ensure_user (update :Update ,source :str ="bot",ai_increment :int =0 ,notify_ui :bool =True ):
    "\n    Единая точка: создаем/обновляем пользователя в БД по tg_id.\n    Возвращает объект User (из БД).\n    "
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
        if notify_ui :
            await _notify_db_unavailable (update ,e ,scope ="ensure_user")
        else :
            _log_db_issue ("ensure_user_silent",e )
        return None 


        # ============ Handlers ============

async def ensure_user_on_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .get (CONTACT_FLOW_KEY ):
        return
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return
    if context .user_data .get (PAYMENT_CONTACT_FLOW_KEY ):
        return
    if not classify_update_need_db (update ,context ):
        logger .debug ("DB guard skipped for navigation message update")
        return
    await ensure_user (update ,source ="bot")


async def start (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
# ensure user exists in DB

    screen_manager .clear_screen (context )
    _reset_states (context )

    start_payload =str ((context .args [0 ]if context .args else "")or "").strip ()
    if start_payload .startswith ("pay_"):
        payment_id =""
        if start_payload !="pay_return":
            payment_id =start_payload [4 :].strip ()
        if payment_id :
            context .user_data ["last_payment_id"]=payment_id
        await _show_screen (
        update ,
        context ,
        "\u0421\u043f\u0430\u0441\u0438\u0431\u043e \u0437\u0430 \u043e\u043f\u043b\u0430\u0442\u0443. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u00ab\u2705 \u042f \u043e\u043f\u043b\u0430\u0442\u0438\u043b \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c\u00bb.",
        parse_mode =None ,
        reply_markup =_payment_return_kb (payment_id ),
        )
        return

    text ="\u0410\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0433\u043e\u0442\u043e\u0432 \u043f\u043e\u043c\u043e\u0447\u044c \u0441 \u0432\u044b\u0431\u043e\u0440\u043e\u043c \u0440\u0430\u0437\u0434\u0435\u043b\u0430."
    await _show_screen (update ,context ,text ,reply_markup =get_main_menu ())


async def main_menu (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    try :
        _reset_states (context )
    except Exception as e :
        _log_db_issue ("main_menu_reset",e )
    try :
        await _show_main_menu_bottom (update ,context )
    except Exception as e :
        logger .warning ("Main menu render fallback: %s",_err_name (e ))
        chat =update .effective_chat
        if chat is not None :
            await _send (context .bot ,chat_id =chat .id ,text ="\u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e",reply_markup =get_main_menu (),parse_mode =None )


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
    if context .user_data .get (PAYMENT_CONTACT_FLOW_KEY ):
        contact =update .message .contact
        phone =(contact .phone_number or "").strip ()
        if not phone :
            await _show_screen (update ,context ,"Не удалось прочитать номер. Отправьте контакт ещё раз.",reply_markup =get_payment_contact_choice_kb ())
            return
        if not await _save_contact_field (update ,context ,phone =phone ):
            return
        await _send_reply_keyboard_remove (update ,context )
        await _show_screen (update ,context ,PAYMENT_CONTACT_SAVED_SCREEN ,reply_markup =get_back_to_menu_kb ())
        await _run_game10_payment_create_flow (update ,context )
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
            await _show_screen (update ,context ,"Контакты уже получены, спасибо!",reply_markup =get_main_menu ())
            return 

    contact =update .message .contact 
    phone =(contact .phone_number or "").strip ()
    if not phone :
        await _show_screen (update ,context ,"Не удалось прочитать номер. Отправьте контакт ещё раз.",reply_markup =get_contact_request_kb ())
        return 
    if not await _save_contact_field (update ,context ,phone =phone ):
        return 

    context .user_data [CONTACT_PHONE_KEY ]=phone 
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=False 
    context .user_data [WAITING_CONTACT_EMAIL_KEY ]=True 
    context .user_data [SKIP_NEXT_EMAIL_KEY ]=True 
    await _show_screen (update ,context ,"Спасибо! Теперь пришлите вашу почту одним сообщением (например: name@example.com).",reply_markup =get_remove_reply_kb ())


async def handle_contact_phone_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .get (PAYMENT_CONTACT_FLOW_KEY ):
        payment_mode =str (context .user_data .get (PAYMENT_CONTACT_MODE_KEY )or "")
        if payment_mode == "email":
            return
        if not update .message or not update .message .text :
            return
        if payment_mode != "phone":
            text =(update .message .text or "").strip ()
            if text .lower ()=="отмена":
                await _send_reply_keyboard_remove (update ,context )
                _clear_payment_contact_flow (context )
                await _show_screen (update ,context ,PAYMENT_CANCELLED_SCREEN ,reply_markup =get_back_to_menu_kb ())
                await _show_main_menu_bottom (update ,context )
            else :
                await _request_payment_contact_screen (update ,context ,variant =_payment_variant_normalized (context .user_data .get (PAYMENT_VARIANT_KEY )))
            return
    if context .user_data .get (PAYMENT_CONTACT_FLOW_KEY )and str (context .user_data .get (PAYMENT_CONTACT_MODE_KEY )or "")=="phone":
        if not update .message or not update .message .text :
            return
        text =(update .message .text or "").strip ()
        if text .lower ()=="отмена":
            await _send_reply_keyboard_remove (update ,context )
            _clear_payment_contact_flow (context )
            await _show_screen (update ,context ,PAYMENT_CANCELLED_SCREEN ,reply_markup =get_back_to_menu_kb ())
            await _show_main_menu_bottom (update ,context )
            return
        normalized =re .sub (r"[^\\d+]","",text )
        if len (re .sub (r"\\D","",normalized ))<10 :
            await _show_screen (update ,context ,"Номер выглядит некорректно. Нажмите кнопку отправки контакта или введите номер ещё раз.",reply_markup =get_payment_contact_choice_kb ())
            return
        if not await _save_contact_field (update ,context ,phone =normalized ):
            return
        await _send_reply_keyboard_remove (update ,context )
        await _show_screen (update ,context ,PAYMENT_CONTACT_SAVED_SCREEN ,reply_markup =get_back_to_menu_kb ())
        await _run_game10_payment_create_flow (update ,context )
        return
    if not context .user_data .get (WAITING_CONTACT_PHONE_KEY ):
        return 
    if not update .message or not update .message .text :
        return 

    text =(update .message .text or "").strip ()
    if text .lower ()=="отмена":
        _reset_states (context )
        await _show_screen (update ,context ,"Действие отменено.",reply_markup =get_main_menu ())
        return 

    normalized =re .sub (r"[^\\d+]","",text )
    if len (re .sub (r"\\D","",normalized ))<10 :
        await _show_screen (update ,context ,"Номер выглядит некорректно. Пример: +79991234567",reply_markup =get_contact_request_kb ())
        return 
    if not await _save_contact_field (update ,context ,phone =normalized ):
        return 

    context .user_data [CONTACT_PHONE_KEY ]=normalized 
    context .user_data [WAITING_CONTACT_PHONE_KEY ]=False 
    context .user_data [WAITING_CONTACT_EMAIL_KEY ]=True 
    context .user_data [SKIP_NEXT_EMAIL_KEY ]=True 
    await _show_screen (update ,context ,"Спасибо! Теперь пришлите вашу почту одним сообщением (например: name@example.com).",reply_markup =get_remove_reply_kb ())


async def handle_contact_email_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    if context .user_data .get (PAYMENT_CONTACT_FLOW_KEY )and str (context .user_data .get (PAYMENT_CONTACT_MODE_KEY )or "")=="email":
        if not update .message or not update .message .text :
            return
        email =(update .message .text or "").strip ().lower ()
        if email =="отмена":
            await _send_reply_keyboard_remove (update ,context )
            _clear_payment_contact_flow (context )
            await _show_screen (update ,context ,PAYMENT_CANCELLED_SCREEN ,reply_markup =get_back_to_menu_kb ())
            await _show_main_menu_bottom (update ,context )
            return
        if not EMAIL_RE .match (email ):
            await _show_screen (update ,context ,"Некорректный email. Введите ещё раз или нажмите «Отмена».",reply_markup =get_payment_contact_choice_kb ())
            return
        if not await _save_contact_field (update ,context ,email =email ):
            return
        await _send_reply_keyboard_remove (update ,context )
        await _show_screen (update ,context ,PAYMENT_CONTACT_SAVED_SCREEN ,reply_markup =get_back_to_menu_kb ())
        await _run_game10_payment_create_flow (update ,context )
        return
    if context .user_data .pop (SKIP_NEXT_EMAIL_KEY ,False ):
        return 
    if not update .message or not update .message .text :
        return 

    waiting_email =bool (context .user_data .get (WAITING_CONTACT_EMAIL_KEY ))
    email =(update .message .text or "").strip ().lower ()
    if waiting_email and email =="отмена":
        _reset_states (context )
        await _show_screen (update ,context ,"Действие отменено.",reply_markup =get_main_menu ())
        return 

    if not EMAIL_RE .match (email ):
        if waiting_email :
            await _show_screen (update ,context ,"Некорректный email. Пример: name@example.com",reply_markup =get_remove_reply_kb ())
        return 

    tg_user =update .effective_user 
    if tg_user is None :
        return 

    snapshot =await _get_contact_snapshot (tg_user .id )
    if snapshot is not None and snapshot .get ("phone")and snapshot .get ("email"):
        _reset_states (context )
        await _show_screen (update ,context ,"Контакты уже получены, спасибо!",reply_markup =get_main_menu ())
        return 

    phone =context .user_data .get (CONTACT_PHONE_KEY )
    if not phone and snapshot is not None :
        phone =snapshot .get ("phone")
    if not phone :
        if waiting_email :
            context .user_data [WAITING_CONTACT_EMAIL_KEY ]=False 
            context .user_data [WAITING_CONTACT_PHONE_KEY ]=True 
        await _show_screen (update ,context ,"Сначала отправьте номер телефона.",reply_markup =get_contact_request_kb ())
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
        line =f"\u2022 {label} - {_format_rub (price_rub )} \u20bd"
        if note :
            line =f"{line} ({note })"
        lines .append (line )
    if lines :
        return lines
    fallback_price =event .get ("price")
    if fallback_price not in (None ,""):
        return [f"\u2022 \u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c - {_format_rub (fallback_price )} \u20bd"]
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
        _log_db_issue ("events_cache_load",e )
        cached =context .user_data .get (EVENTS_CACHE_KEY )
        if isinstance (cached ,list )and cached :
            return cached
        await _show_screen (
        update ,
        context ,
        "\u26a0\ufe0f \u0421\u043f\u0438\u0441\u043e\u043a \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0439 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0447\u0443\u0442\u044c \u043f\u043e\u0437\u0436\u0435.",
        reply_markup =InlineKeyboardMarkup ([
        [InlineKeyboardButton ("\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c",callback_data ="event_list_refresh")],
        [InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
        ]),
        )
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
    await show_events_list_screen (update ,context )


async def event_list_refresh (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    await show_events_list_screen (update ,context ,force_refresh =True )


async def event_list_next (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    page =int (context .user_data .get (EVENTS_LIST_PAGE_KEY )or 0 )+1
    await show_events_list_screen (update ,context ,page =page )


async def event_list_prev (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
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
    await show_event_detail_screen (update ,context ,event_id )


async def event_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )
    try :
        event_id =int ((query .data or "").split (":",1 )[1 ])
    except Exception :
        await _show_screen (update ,context ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0447\u0430\u0442 \u043f\u043e \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044e.",reply_markup =get_back_to_menu_kb ())
        return
    user_id =update .effective_user .id
    chat_histories [user_id ]=[]
    context .user_data [WAITING_LEAD_KEY ]=None
    context .user_data [AI_MODE_KEY ]=True
    context .user_data [ASSISTANT_SOURCE_KEY ]="event"
    context .user_data [ASSISTANT_EVENT_ID_KEY ]=event_id
    context .user_data .pop (PRODUCT_FOCUS_KEY ,None )
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


    await _send_events_list (update ,None ,context ,from_callback =True )


async def show_events_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    await _send_events_list (update ,None ,context ,from_callback =False )


async def show_courses (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )


    await _send_courses_list (update ,context ,offset =0 ,from_callback =True )


async def show_courses_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    await _send_courses_list (update ,context ,offset =0 ,from_callback =False )


async def show_courses_page (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    try :
        offset =int ((query .data or "").split (":")[1 ])
    except Exception :
        offset =0 


    await _send_courses_list (update ,context ,offset =max (offset ,0 ),from_callback =True )


async def show_private_channel (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )


    await _show_screen (
    update ,
    context ,
    GAME10_SCREEN_TEXT ,
    parse_mode ="Markdown",
    reply_markup =_game10_kb_for_update (update ),
    )


async def show_game10_description (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query :
        await _answer (query )
    await _show_screen (
    update ,
    context ,
    GAME10_DESCRIPTION_SCREEN_TEXT ,
    reply_markup =get_game10_description_kb (),
    )


async def private_channel_payment_info (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    await _answer (query )
    await _run_game10_payment_create_flow (update ,context ,variant =PAYMENT_VARIANT_MAIN )



async def game10_pay_refresh (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    await _answer (query )
    await _run_game10_payment_create_flow (update ,context ,variant =PAYMENT_VARIANT_MAIN ,refresh_hint =True )



async def game10_pay_check (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    try :
        await _answer (query )
    except Exception :
        pass
    data =str (query .data or "")
    payment_id =data .split (":",1 )[1 ].strip ()if ":" in data else ""
    if not payment_id :
        payment_id =str (context .user_data .get ("last_payment_id")or "").strip ()
    if not payment_id :
        await _show_screen (update ,context ,"\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d id \u043f\u043b\u0430\u0442\u0435\u0436\u0430. \u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u0440\u0430\u0437\u0434\u0435\u043b \u043e\u043f\u043b\u0430\u0442\u044b \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.",reply_markup =_game10_kb_for_update (update ))
        return
    context .user_data ["last_payment_id"]=payment_id
    retry_kb =_get_last_game10_payment_ui_kb (context ,payment_id )or _game10_kb_for_update (update )
    await _show_screen (update ,context ,PAYMENT_CHECKING_SCREEN ,reply_markup =retry_kb )
    user =update .effective_user
    result =await _check_game10_payment_status_backend (payment_id ,tg_id =user .id if user else None )
    if not isinstance (result ,dict )or not result .get ("ok"):
        await _show_screen (update ,context ,"Could not verify payment now. Please retry in a minute.",reply_markup =retry_kb )
        return
    status =str (result .get ("status")or "").strip ().lower ()
    outcome =str (result .get ("result")or "").strip ().lower ()
    error_type =str (result .get ("error_type")or "").strip ()
    if bool (result .get ("already_in_channel"))or outcome =="already_member":
        _clear_payment_runtime_state (context )
        await _show_screen (update ,context ,PAYMENT_ALREADY_IN_CHANNEL_SCREEN ,reply_markup =_game10_kb_for_update (update ))
        return
    if status =="succeeded"and outcome =="invite_failed":
        error_norm =error_type .lower ()
        if error_norm in {"forbidden","chatnotfound"}:
            await _show_screen (update ,context ,"Bot cannot message you now. Send /start and check again.",reply_markup =retry_kb )
            return
        await _show_screen (update ,context ,"Access delivery failed. Please contact admin and retry.",reply_markup =retry_kb )
        return
    if status =="succeeded":
        _clear_payment_runtime_state (context )
        await _show_screen (update ,context ,PAYMENT_STATUS_CONFIRMED_SCREEN ,reply_markup =_game10_kb_for_update (update ))
        return
    if status in {"pending","waiting_for_capture","created"}:
        await _show_screen (update ,context ,"Payment is still processing. Please try again in a minute.",reply_markup =retry_kb )
        return
    if status in {"canceled","cancelled"}:
        _clear_payment_runtime_state (context )
        await _show_screen (update ,context ,PAYMENT_STATUS_CANCELED_SCREEN ,reply_markup =retry_kb )
        return
    await _show_screen (update ,context ,f"Payment status: {status or 'unknown'}",reply_markup =retry_kb )


async def pay_contact_phone (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    await _answer (query )
    if not context .user_data .get (PAYMENT_CONTACT_FLOW_KEY ):
        await _request_payment_contact_screen (update ,context ,variant =_payment_variant_normalized (context .user_data .get (PAYMENT_VARIANT_KEY )))
        return
    context .user_data [PAYMENT_CONTACT_MODE_KEY ]="phone"
    await _show_screen (update ,context ,PAYMENT_ASK_PHONE_SCREEN ,reply_markup =get_payment_contact_choice_kb ())
    chat =update .effective_chat
    if chat is not None :
        await _send (context .bot ,chat_id =chat .id ,text ="Нажмите кнопку ниже, чтобы отправить номер.",reply_markup =get_contact_request_kb ())


async def pay_contact_email (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    await _answer (query )
    if not context .user_data .get (PAYMENT_CONTACT_FLOW_KEY ):
        await _request_payment_contact_screen (update ,context ,variant =_payment_variant_normalized (context .user_data .get (PAYMENT_VARIANT_KEY )))
        return
    context .user_data [PAYMENT_CONTACT_MODE_KEY ]="email"
    await _send_reply_keyboard_remove (update ,context )
    await _show_screen (update ,context ,PAYMENT_ASK_EMAIL_SCREEN ,reply_markup =get_payment_contact_choice_kb ())


async def pay_contact_cancel (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is None :
        return
    await _answer (query )
    await _send_reply_keyboard_remove (update ,context )
    _clear_payment_runtime_state (context )
    await _show_screen (update ,context ,PAYMENT_CANCELLED_SCREEN ,reply_markup =get_back_to_menu_kb ())
    await _show_main_menu_bottom (update ,context )


    # --------- Consultations / Gestalt ---------

async def show_consultations (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )


    await _show_screen (update ,context ,
    GESTALT_SHORT_SCREEN_1 ,
    parse_mode ="Markdown",
    reply_markup =get_consultations_menu (),
    )


async def show_formats_and_prices (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    _reset_states (context )


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


    await _show_screen (update ,context ,
    "\U0001f4e9 *\u0417\u0430\u043f\u0438\u0441\u044c \u043d\u0430 \u0438\u043d\u0434\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d\u0443\u044e \u0442\u0435\u0440\u0430\u043f\u0438\u044e*\n\n"
    "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c:\n"
    "1) \u0418\u043c\u044f\n"
    "2) \u0422\u0435\u043b\u0435\u0444\u043e\u043d \u0438\u043b\u0438 @username\n"
    "3) \u041a\u043e\u0440\u043e\u0442\u043a\u043e \u0437\u0430\u043f\u0440\u043e\u0441 (\u043f\u043e \u0436\u0435\u043b\u0430\u043d\u0438\u044e)\n\n"
    "\u041f\u0440\u0438\u043c\u0435\u0440: \u0418\u0432\u0430\u043d, +7..., \u0445\u043e\u0447\u0443 \u043c\u0435\u043d\u044c\u0448\u0435 \u0442\u0440\u0435\u0432\u043e\u0433\u0438",
    parse_mode ="Markdown",
    reply_markup =get_back_to_menu_kb (),
    )


async def begin_booking_group (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )
    context .user_data [AI_MODE_KEY ]=False 
    context .user_data [WAITING_LEAD_KEY ]="group"


    await _show_screen (update ,context ,
    "\U0001f4e9 *\u0417\u0430\u043f\u0438\u0441\u044c \u0432 \u0442\u0435\u0440\u0430\u043f\u0435\u0432\u0442\u0438\u0447\u0435\u0441\u043a\u0443\u044e \u0433\u0440\u0443\u043f\u043f\u0443*\n\n"
    "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c:\n"
    "1) \u0418\u043c\u044f\n"
    "2) \u0422\u0435\u043b\u0435\u0444\u043e\u043d \u0438\u043b\u0438 @username\n"
    "3) \u041a\u043e\u0440\u043e\u0442\u043a\u043e \u043e\u0436\u0438\u0434\u0430\u043d\u0438\u044f \u043e\u0442 \u0433\u0440\u0443\u043f\u043f\u044b (\u043f\u043e \u0436\u0435\u043b\u0430\u043d\u0438\u044e)\n\n"
    "\u041f\u0440\u0438\u043c\u0435\u0440: \u0410\u043d\u043d\u0430, @anna, \u0445\u043e\u0447\u0443 \u043d\u0430\u0443\u0447\u0438\u0442\u044c\u0441\u044f \u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c \u043e \u0447\u0443\u0432\u0441\u0442\u0432\u0430\u0445",
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


    user_id =update .effective_user .id 
    chat_histories [user_id ]=[]# reset in-memory history on /start

    context .user_data [WAITING_LEAD_KEY ]=None 
    context .user_data [AI_MODE_KEY ]=True 
    context .user_data [ASSISTANT_SOURCE_KEY ]="consult"
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )
    context .user_data [PRODUCT_FOCUS_KEY ]="gestalt"

    await _show_screen (update ,context ,
    ASSISTANT_GREETING ,
    reply_markup =get_back_to_menu_kb (),
    )


async def show_course_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )


    user_id =update .effective_user .id 
    chat_histories [user_id ]=[]

    context .user_data [WAITING_LEAD_KEY ]=None 
    context .user_data [AI_MODE_KEY ]=True 
    context .user_data [ASSISTANT_SOURCE_KEY ]="course"
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )
    context .user_data [PRODUCT_FOCUS_KEY ]="getcourse"

    await _show_screen (
    update ,
    context ,
    COURSE_ASSISTANT_GREETING ,
    reply_markup =get_back_to_menu_kb (),
    )


async def game10_questions (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    await _answer (query )


    user_id =update .effective_user .id
    chat_histories [user_id ]=[]

    context .user_data [WAITING_LEAD_KEY ]=None
    context .user_data [AI_MODE_KEY ]=True
    context .user_data [ASSISTANT_SOURCE_KEY ]="game10"
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )
    context .user_data [PRODUCT_FOCUS_KEY ]="game10"

    await _show_screen (
    update ,
    context ,
    GAME10_ASSISTANT_GREETING ,
    parse_mode ="Markdown",
    reply_markup =get_back_to_menu_kb (),
    )


async def _show_consultations_from_text (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _reset_states (context )
    message =update .effective_message 
    if message is not None :
        await _show_screen (update ,context ,"Выберите формат консультации 👇",reply_markup =get_consultations_menu ())


def _auto_ai_rate_limited (context :ContextTypes .DEFAULT_TYPE )->bool :
    now_ts =datetime .utcnow ().timestamp ()
    raw =context .user_data .get (AUTO_AI_REPLY_TIMESTAMPS_KEY )or []
    kept :list [float ]=[]
    for item in raw :
        try :
            ts =float (item )
        except Exception :
            continue
        if now_ts -ts <=AUTO_AI_RATE_LIMIT_WINDOW_SEC :
            kept .append (ts )
    if len (kept )>=AUTO_AI_RATE_LIMIT_MAX :
        context .user_data [AUTO_AI_REPLY_TIMESTAMPS_KEY ]=kept [-AUTO_AI_RATE_LIMIT_MAX :]
        return True
    kept .append (now_ts )
    context .user_data [AUTO_AI_REPLY_TIMESTAMPS_KEY ]=kept [-AUTO_AI_RATE_LIMIT_MAX :]
    return False


def _build_ai_request_message (context :ContextTypes .DEFAULT_TYPE ,user_message :str ,*,response_mode :str ="default")->str :
    assistant_source =str (context .user_data .get (ASSISTANT_SOURCE_KEY )or "").strip ().lower ()
    ai_message =user_message
    if assistant_source =="consult":
        ai_message =f"[FOCUS:GESTALT]\n{user_message }"
        if response_mode =="sales":
            ai_message =f"[FOCUS:GESTALT]\n[SALES_MODE]\n{user_message }"
        return ai_message
    if assistant_source =="course":
        ai_message =f"\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442: \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043e \u043a\u0443\u0440\u0441\u0435 GetCourse.\n{user_message }"
        if response_mode =="sales":
            ai_message =f"[SALES_MODE]\n{ai_message }"
        return ai_message
    if assistant_source =="game10":
        ai_message =f"[FOCUS:GAME10]\n{user_message }"
        if response_mode =="sales":
            ai_message =f"[FOCUS:GAME10]\n[SALES_MODE]\n{user_message }"
        return ai_message
    if assistant_source =="event":
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
    product_focus =str (context .user_data .get (PRODUCT_FOCUS_KEY )or "").strip ().lower ()
    if product_focus and not assistant_source :
        ai_message =f"[FOCUS:{product_focus .upper ()}]\n{ai_message }"
    if response_mode =="sales":
        if ai_message .startswith ("[FOCUS:"):
            lines =ai_message .split ("\n",1 )
            head =lines [0 ]
            tail =lines [1 ] if len (lines )>1 else ""
            ai_message =f"{head }\n[SALES_MODE]\n{tail }".rstrip ()
        else :
            ai_message =f"[SALES_MODE]\n{ai_message }"
    return ai_message


async def _send_ai_response (
update :Update ,
context :ContextTypes .DEFAULT_TYPE ,
*,
user_message :str ,
response_mode :str ,
reply_markup =None ,
)->bool :
    message =update .message
    tg_user =update .effective_user
    if message is None or tg_user is None :
        return False

    user_db =await ensure_user (update ,source ="bot",notify_ui =False )
    user_id =tg_user .id
    history =chat_histories .get (user_id ,[])
    ai_message =_build_ai_request_message (context ,user_message ,response_mode =response_mode )

    typing_indicator =None
    if update .effective_chat is not None :
        typing_indicator =TypingIndicator (context .bot ,update .effective_chat .id )
        await typing_indicator .start ()

    try :
        response ,new_history =await ai_service .chat (
        ai_message ,
        history ,
        tg_id =tg_user .id ,
        response_mode =response_mode ,
        )
        chat_histories [user_id ]=new_history
        if user_db is not None :
            try :
                async with db .async_session ()as session :
                    activity_service =ActivityService (session )
                    await activity_service .upsert (
                    user_id =user_db .id ,
                    last_activity_at =datetime .utcnow (),
                    ai_increment =1 ,
                    )
                    await session .commit ()
            except Exception as e :
                _log_db_issue ("ai_activity",e )
        await _reply (message ,response ,reply_markup =reply_markup )
        return True
    except Exception as e :
        logger .exception ("Assistant error: %s",e )
        await _reply (
        message ,
        "\u0421\u0435\u0439\u0447\u0430\u0441 \u043d\u0435 \u043f\u043e\u043b\u0443\u0447\u0438\u043b\u043e\u0441\u044c \u043e\u0442\u0432\u0435\u0442\u0438\u0442\u044c. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0447\u0443\u0442\u044c \u043f\u043e\u0437\u0436\u0435.",
        reply_markup =reply_markup ,
        )
        return False
    finally :
        if typing_indicator is not None :
            await typing_indicator .stop ()


async def _route_detected_intent (update :Update ,context :ContextTypes .DEFAULT_TYPE ,intent :str )->bool :
    context .user_data [AI_MODE_KEY ]=False
    context .user_data .pop (ASSISTANT_SOURCE_KEY ,None )
    context .user_data .pop (ASSISTANT_EVENT_ID_KEY ,None )
    _clear_product_focus (context )
    if intent =="MENU":
        await menu_command (update ,context )
        return True
    if intent =="HELP":
        await show_help (update ,context )
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
    if intent =="GAME10":
        if update .callback_query :
            await show_private_channel (update ,context )
        else :
            _reset_states (context )
            await _show_screen (
            update ,
            context ,
            GAME10_SCREEN_TEXT ,
            parse_mode ="Markdown",
            reply_markup =_game10_kb_for_update (update ),
            )
        return True
    return False

def _extract_navigation_intent_from_text_message (update :Update )->str |None :
    message =update .effective_message
    if message is None :
        return None
    text =(getattr (message ,"text",None )or "").strip ()
    if not text or text .startswith ("/"):
        return None
    return detect_intent (text )

async def handle_navigation_text_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _apply_focus_timeout (context )
    intent =_extract_navigation_intent_from_text_message (update )
    if not intent :
        return
    routed =await _route_detected_intent (update ,context ,intent )
    if routed :
        raise ApplicationHandlerStop

async def handle_ai_message (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _apply_focus_timeout (context )
    if context .user_data .get (WAITING_LEAD_KEY ):
        return
    if context .user_data .get (WAITING_CONTACT_PHONE_KEY )or context .user_data .get (WAITING_CONTACT_EMAIL_KEY ):
        return
    if not context .user_data .get (AI_MODE_KEY ):
        return

    message =update .message
    if message is None :
        return
    user_message =(message .text or "").strip ()
    if not user_message or user_message .startswith ("/"):
        return

    intent =detect_intent (user_message )
    if intent :
        return

    assistant_source =str (context .user_data .get (ASSISTANT_SOURCE_KEY )or "").strip ().lower ()
    product_focus =str (context .user_data .get (PRODUCT_FOCUS_KEY )or "").strip ().lower ()
    if not assistant_source and not product_focus :
        context .user_data [AI_MODE_KEY ]=False
        await _show_screen (update ,context ,ASSISTANT_ENTRY_HINT_TEXT ,reply_markup =get_back_to_menu_kb ())
        return

    if not context .user_data .get (ASSISTANT_SOURCE_KEY )and not context .user_data .get (PRODUCT_FOCUS_KEY ):
        focus_candidate =detect_product_focus (user_message )
        if focus_candidate :
            context .user_data [PRODUCT_FOCUS_KEY ]=focus_candidate

    await _send_ai_response (
    update ,
    context ,
    user_message =user_message ,
    response_mode ="assistant",
    )

async def handle_text_outside_assistant (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    _apply_focus_timeout (context )
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
    if not text or text .startswith ("/"):
        return

    intent =detect_intent (text )
    if intent :
        return

    await _show_screen (update ,context ,ASSISTANT_ENTRY_HINT_TEXT ,reply_markup =get_back_to_menu_kb ())

async def show_help (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query
    if query is not None :
        await _answer (query )
    _reset_states (context )

    text =(
    "\U0001f4da *\u041f\u043e\u043c\u043e\u0449\u044c*\n\n"
    "\u2022 /start \u2014 \u043f\u0435\u0440\u0435\u0437\u0430\u043f\u0443\u0441\u043a\n"
    "\u2022 \U0001f4c5 \u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f \u2014 \u0441\u043f\u0438\u0441\u043e\u043a \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0438\u0445\n"
    "\u2022 \U0001f393 \u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u0438 \u2014 \u0433\u0435\u0448\u0442\u0430\u043b\u044c\u0442 + \u0437\u0430\u043f\u0438\u0441\u044c\n"
    "\u2022 \U0001f91d \u0410\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0420\u0435\u043d\u0430\u0442\u044b \u2014 \u0432\u043e\u043f\u0440\u043e\u0441\u044b\n\n"
    "\u0415\u0441\u043b\u0438 \u043d\u0435 \u043f\u043e\u043b\u0443\u0447\u0430\u0435\u0442\u0441\u044f \u2014 \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0441\u044e\u0434\u0430, \u044f \u043f\u043e\u043c\u043e\u0433\u0443 \U0001f642"
    )
    await _show_screen (update ,context ,text ,reply_markup =get_back_to_menu_kb (),parse_mode ="Markdown")

async def course_link_unavailable (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query ,"\u0421\u0441\u044b\u043b\u043a\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430, \u043c\u044b \u043e\u0431\u043d\u043e\u0432\u0438\u043c \u0435\u0435 \u043f\u043e\u0441\u043b\u0435 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u0438.",show_alert =True )


    # --------- Errors / Retry ---------

async def rag_debug_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    message =update .effective_message
    user =update .effective_user
    if message is None or user is None :
        return
    if ADMIN_CHAT_ID and str (user .id )!=str (ADMIN_CHAT_ID ):
        await _reply (message ,"\u041a\u043e\u043c\u0430\u043d\u0434\u0430 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0443.")
        return

    query =" ".join (context .args or []).strip ()or "\u0438\u0433\u0440\u0430 10:0"
    snapshot =ai_service .rag_debug_snapshot (query )
    collections =snapshot .get ("collections")or {}
    trace =snapshot .get ("trace")or {}
    last_trace =snapshot .get ("last_response_trace")or {}
    discovered =snapshot .get ("discovered_collections")or list (collections .keys ())
    lines =[
    f"RAG enabled: {snapshot .get ('enabled')}",
    f"Base dir: {snapshot .get ('base_dir')}",
    f"Query: {query}",
    f"Access: {'admin-only' if ADMIN_CHAT_ID else 'ADMIN_CHAT_ID not set (open command)'}",
    f"Collections: {', '.join (map (str ,discovered )) if discovered else '-'}",
    f"Trace: collection={trace .get ('rag_collection','-')} requested={trace .get ('rag_requested_collection','-')} hits={trace .get ('rag_hits',0)} used={trace .get ('rag_used',False)} fallback_default={trace .get ('rag_fallback_to_default',False)}",
    f"Trace scores: {trace .get ('rag_top_scores') or []}",
    f"Last response trace: events={last_trace .get ('events_used',last_trace .get ('used_events',False))}({last_trace .get ('events_count',last_trace .get ('used_events_count',0))}) rag={last_trace .get ('rag_used',False)}[{last_trace .get ('rag_used_collection',last_trace .get ('rag_collection','-'))}] hits={last_trace .get ('rag_hits',0)} fallback_model={last_trace .get ('fallback_to_model',False)}",
    "",
    ]
    for name in discovered :
        data =collections .get (name )or {}
        lines .append (f"[{name}] dir={data .get ('dir')}")
        if data .get ("error"):
            lines .append (f"  error: {data .get ('error')}")
            lines .append ("")
            continue
        lines .append (f"  docs: {data .get ('docs',0)} | chunks: {data .get ('chunks',0)} | confidence: {data .get ('confidence','-')}")
        hits =data .get ("hits")or []
        if not hits :
            lines .append ("  hits: none")
        else :
            for idx ,hit in enumerate (hits ,start =1 ):
                title =str (hit .get ('title')or '-')
                source =str (hit .get ('source')or '-')
                score =hit .get ('score')
                excerpt =str (hit .get ('text')or '').replace ('\n',' ')
                lines .append (f"  {idx}. {title} ({source}) score={score}: {excerpt}")
        lines .append ("")
    payload ="\n".join (lines )[:3900]
    await _reply (message ,payload )


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
    error_obj =context .error if isinstance (context .error ,Exception )else None
    logger .exception ("Unhandled error type: %s",_err_name (error_obj ))
    if not isinstance (update ,Update ):
        return
    if _is_db_exception (error_obj ):
        await _notify_db_unavailable (update ,error_obj ,scope ="on_error")
        return
    query =getattr (update ,"callback_query",None )
    if query is not None :
        try :
            await _answer (query ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u00ab\u0412 \u043c\u0435\u043d\u044e\u00bb.")
        except Exception :
            pass


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
        await _answer (query ,"\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id 
            result =await crm_service .add_attendee_by_tg_id (event_id ,tg_id )
            if not result .get ("ok")and result .get ("error")=="event_not_found":
                await _answer (query ,"\u0421\u043e\u0431\u044b\u0442\u0438\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e",show_alert =True )
                return 
            if not result .get ("ok")and result .get ("error")=="user_not_found":
                await _answer (query ,"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",show_alert =True )
                return 
            await session .commit ()
            if str (context .user_data .get (SCREEN_KIND_KEY )or "")=="event_detail"and int (context .user_data .get (SCREEN_EVENT_ID_KEY )or 0 )==event_id :
                await show_event_detail_screen (update ,context ,event_id )
            else :
                await _safe_edit_reply_markup (
                query ,
                reply_markup =get_event_actions_kb (event_id ,registered =True ),
                )
            await _answer (query ,"\u0412\u044b \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u044b!"if not result .get ("already")else "\u0412\u044b \u0443\u0436\u0435 \u0431\u044b\u043b\u0438 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u044b")
    except Exception as e :
        _log_db_issue ("event_register",e )
        _remember_pending_event_action (context ,update ,action ="event_register",event_id =event_id )
        _set_screen_meta (context ,kind ="event_detail",event_id =event_id )
        await _show_screen (
        update ,
        context ,
        "\u26a0\ufe0f \u0421\u0435\u0439\u0447\u0430\u0441 \u0431\u0430\u0437\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430, \u043d\u043e \u043c\u044b \u043f\u0440\u0438\u043d\u044f\u043b\u0438 \u0437\u0430\u043f\u0440\u043e\u0441 \u043d\u0430 \u0437\u0430\u043f\u0438\u0441\u044c. \u041c\u044b \u0441\u0432\u044f\u0436\u0435\u043c\u0441\u044f \u0441 \u0432\u0430\u043c\u0438.",
        reply_markup =InlineKeyboardMarkup ([
        [InlineKeyboardButton ("\u041a \u0441\u043f\u0438\u0441\u043a\u0443",callback_data ="events_list")],
        [InlineKeyboardButton ("\u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
        ]),
        )


async def event_cancel (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    try :
        event_id =int (query .data .split (":")[1 ])
    except Exception :
        await _answer (query ,"\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id 
            result =await crm_service .remove_attendee_by_tg_id (event_id ,tg_id )
            if not result .get ("ok")and result .get ("error")=="event_not_found":
                await _answer (query ,"\u0421\u043e\u0431\u044b\u0442\u0438\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e",show_alert =True )
                return 
            if not result .get ("ok")and result .get ("error")=="user_not_found":
                await _answer (query ,"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",show_alert =True )
                return 
            await session .commit ()
            if str (context .user_data .get (SCREEN_KIND_KEY )or "")=="event_detail"and int (context .user_data .get (SCREEN_EVENT_ID_KEY )or 0 )==event_id :
                await show_event_detail_screen (update ,context ,event_id )
            else :
                await _safe_edit_reply_markup (
                query ,
                reply_markup =get_event_actions_kb (event_id ,registered =False ),
                )
            await _answer (query ,"\u0417\u0430\u043f\u0438\u0441\u044c \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430"if result .get ("removed")else "\u0412\u044b \u043d\u0435 \u0431\u044b\u043b\u0438 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u044b")
    except Exception as e :
        await _notify_db_unavailable (update ,e ,scope ="event_cancel")


async def event_pay (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    query =update .callback_query 
    await _answer (query )

    user_db =await ensure_user (update ,source ="bot")
    if user_db is None :
        return 

    try :
        event_id =int (query .data .split (":")[1 ])
    except Exception :
        await _answer (query ,"\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 event_id",show_alert =True )
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            event_service =EventService (session )
            event =await event_service .get_by_id (event_id )
            if not event :
                await _answer (query ,"\u0421\u043e\u0431\u044b\u0442\u0438\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e",show_alert =True )
                return 

            price_value =event .price 
            amount =int (price_value )if price_value is not None else 0 
            if amount <=0 :
                await _answer (query ,"\u041e\u043f\u043b\u0430\u0442\u0430 \u0434\u043b\u044f \u044d\u0442\u043e\u0433\u043e \u0441\u043e\u0431\u044b\u0442\u0438\u044f \u043f\u043e\u043a\u0430 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430",show_alert =True )
                return 

            crm_service =CRMService (session )
            result =await crm_service .create_payment_for_user (
            tg_id =update .effective_user .id if update .effective_user else user_db .tg_id ,
            event_id =event_id ,
            amount =amount ,
            source ="yookassa",
            )
            if result is None :
                await _answer (query ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u043b\u0430\u0442\u0435\u0436",show_alert =True )
                return 

            await session .commit ()

            payment_link =f"https://pay.example.local/yookassa?payment_id={result ['id']}"
            event_link_part =(
            f"\n\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u044f \u043d\u0430 GetCourse: {event .link_getcourse }"
            if _is_valid_http_url (event .link_getcourse )
            else ""
            )
            invite_part =(
            f"\n\u041f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043e\u043f\u043b\u0430\u0442\u044b \u0432\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u0432 \u043a\u0430\u043d\u0430\u043b: {TG_PRIVATE_CHANNEL_INVITE_LINK }"
            if TG_PRIVATE_CHANNEL_INVITE_LINK 
            else "\n\u041f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043e\u043f\u043b\u0430\u0442\u044b \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442 \u0441\u0441\u044b\u043b\u043a\u0443 \u0432 \u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u043a\u0430\u043d\u0430\u043b."
            )
            await _send (context .bot ,
            chat_id =update .effective_chat .id ,
            text =(
            "\u041f\u043b\u0430\u0442\u0435\u0436 \u0441\u043e\u0437\u0434\u0430\u043d (pending).\n"
            f"\u0421\u0441\u044b\u043b\u043a\u0430 \u0434\u043b\u044f \u043e\u043f\u043b\u0430\u0442\u044b: {payment_link }\n"
            "\u0415\u0441\u043b\u0438 \u043d\u0443\u0436\u0435\u043d \u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u0441\u043f\u043e\u0441\u043e\u0431, \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \u00ab\u0421\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f \u0441 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u043e\u043c\u00bb."
            f"{event_link_part }"
            f"{invite_part }"
            ),
            )
    except Exception as e :
        await _notify_db_unavailable (update ,e ,scope ="event_pay")


async def menu_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    try :
        _reset_states (context )
    except Exception as e :
        _log_db_issue ("menu_command_reset",e )
    if update .effective_message :
        try :
            await _show_main_menu_bottom (update ,context )
        except Exception as e :
            logger .warning ("Menu command fallback: %s",_err_name (e ))
            chat =update .effective_chat
            if chat is not None :
                await _send (context .bot ,chat_id =chat .id ,text ="\u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e",reply_markup =get_main_menu (),parse_mode =None )


async def mark_paid_dev (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    message =update .effective_message 
    user =update .effective_user 
    if message is None or user is None :
        return 

    if not _is_admin_user_id (user .id ):
        await _reply (message ,"\u041a\u043e\u043c\u0430\u043d\u0434\u0430 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u0431\u043e\u0442\u0430.")
        return 

    args =context .args or []
    if len (args )!=2 :
        await _reply (message ,"\u0424\u043e\u0440\u043c\u0430\u0442: /mark_paid <tg_id> <event_id>")
        return 

    try :
        tg_id =int (args [0 ])
        event_id =int (args [1 ])
    except ValueError :
        await _reply (message ,"tg_id \u0438 event_id \u0434\u043e\u043b\u0436\u043d\u044b \u0431\u044b\u0442\u044c \u0447\u0438\u0441\u043b\u0430\u043c\u0438.")
        return 

    try :
        db .init_db ()
        async with db .async_session ()as session :
            crm_service =CRMService (session )
            target_user =await crm_service ._get_user_by_tg_id (tg_id )
            if target_user is None :
                await _reply (message ,"Пользователь не найден.")
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
                await _reply (message ,"Платеж не найден.")
                return 

            await crm_service .mark_payment_status (payment_id ,"paid")
            await session .commit ()

        await _reply (message ,
        f"\u041f\u043b\u0430\u0442\u0451\u0436 #{payment_id } \u043e\u0442\u043c\u0435\u0447\u0435\u043d \u043a\u0430\u043a paid \u0434\u043b\u044f tg_id={tg_id }, event_id={event_id }."
        )
        if TG_PRIVATE_CHANNEL_INVITE_LINK :
            await _send (context .bot ,
            chat_id =tg_id ,
            text =(
            "\u041e\u043f\u043b\u0430\u0442\u0430 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430. \u0412\u043e\u0442 \u0441\u0441\u044b\u043b\u043a\u0430 \u0432 \u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u043a\u0430\u043d\u0430\u043b:\n"
            f"{TG_PRIVATE_CHANNEL_INVITE_LINK }"
            ),
            )
    except Exception as e :
        logger .exception ("Ошибка в /mark_paid: %s",e )
        await _reply (message ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043c\u0435\u0442\u0438\u0442\u044c \u043e\u043f\u043b\u0430\u0442\u0443. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u043b\u043e\u0433\u0438.")


async def testpay10_command (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    message =update .effective_message
    user =update .effective_user
    if message is None or user is None :
        return
    if not PAYMENTS_TEST_ENABLED :
        await _reply (message ,"Тестовый режим оплаты выключен.")
        return
    if not _is_admin_user_id (user .id ):
        await _reply (message ,"Команда доступна только администратору.")
        return

    await _reply (message ,"Создаю тестовый платёж...")
    result =await _create_test_payment_backend (user .id )
    if not isinstance (result ,dict )or not result .get ("ok"):
        await _reply (message ,"Не удалось создать тестовый платёж.")
        return
    payment_id =str (result .get ("payment_id")or "").strip ()
    confirmation_url =str (result .get ("confirmation_url")or "").strip ()
    context .user_data ["last_payment_id"]=payment_id
    if not confirmation_url :
        await _reply (message ,"Платёж создан, но ссылка оплаты не получена.")
        return

    chat =update .effective_chat
    if chat is None :
        return
    text =(
    f"\u0422\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u043f\u043b\u0430\u0442\u0451\u0436 {PAYMENTS_TEST_AMOUNT_RUB } \u20bd.\n"
    f"payment_id: {payment_id or '-'}\n"
    f"{confirmation_url }"
    )
    kb =InlineKeyboardMarkup ([
    [InlineKeyboardButton ("\u2705 \u042f \u043e\u043f\u043b\u0430\u0442\u0438\u043b \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",callback_data =f"pay_check:{payment_id }")],
    [InlineKeyboardButton ("\u21a9\ufe0f \u0412 \u043c\u0435\u043d\u044e",callback_data ="main_menu")],
    ])
    try :
        await _send (
        context .bot ,
        chat_id =chat .id ,
        text =text ,
        parse_mode =None ,
        disable_web_page_preview =True ,
        reply_markup =kb ,
        )
    except BadRequest :
        # Safety net: retry plain text explicitly without entity parsing.
        try :
            await context .bot .send_message (
            chat_id =chat .id ,
            text =_t (text ,label ="send")or "",
            parse_mode =None ,
            disable_web_page_preview =True ,
            reply_markup =normalize_ui_reply_markup (kb ),
            )
        except Exception :
            await _reply (message ,"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.")
            return


async def pay_debug (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    message =update .effective_message 
    user =update .effective_user 
    if message is None or user is None :
        return 
    if not _is_admin_user_id (user .id ):
        await _reply (message ,"Команда доступна только админу.")
        return 
    args =context .args or []
    try :
        tg_id =int (args [0 ])if args else int (user .id )
    except Exception :
        await _reply (message ,"Формат: /pay_debug [tg_id]")
        return 
    is_paid =await _is_private_channel_paid_local (tg_id )
    last_payment =await _get_last_game10_payment_local (tg_id )
    if not last_payment :
        await _reply (message ,f"tg_id={tg_id}\nprivate_channel_paid={is_paid}\nlast_payment: not found")
        return 
    await _reply (
    message ,
    (
    f"tg_id={tg_id}\n"
    f"private_channel_paid={is_paid}\n"
    f"last_payment_id={last_payment .get ('payment_id')or '-'}\n"
    f"last_payment_variant={last_payment .get ('product')or '-'}\n"
    f"last_payment_status={last_payment .get ('status')or '-'}\n"
    f"paid_at={last_payment .get ('paid_at')or '-'}\n"
    f"has_phone={bool (last_payment .get ('has_phone'))}\n"
    f"has_email={bool (last_payment .get ('has_email'))}"
    ),
    )


async def handle_chat_join_request (update :Update ,context :ContextTypes .DEFAULT_TYPE ):
    join_request =getattr (update ,"chat_join_request",None )
    if join_request is None :
        return 
    if TELEGRAM_PRIVATE_CHANNEL_ID and str (join_request .chat .id )!=str (TELEGRAM_PRIVATE_CHANNEL_ID ):
        return 
    user =getattr (join_request ,"from_user",None )
    if user is None :
        return 
    is_paid =await _is_private_channel_paid_local (user .id )
    action =decide_private_channel_join_action (
    request_chat_id =join_request .chat .id ,
    configured_channel_id =TELEGRAM_PRIVATE_CHANNEL_ID ,
    is_paid =is_paid ,
    )
    if action =="ignore":
        return 
    if action =="approve":
        try :
            await context .bot .approve_chat_join_request (chat_id =join_request .chat .id ,user_id =user .id )
        except Exception as e :
            logger .warning ("Approve chat join request failed: %s",e .__class__ .__name__ )
        return 
    try :
        await context .bot .decline_chat_join_request (chat_id =join_request .chat .id ,user_id =user .id )
    except Exception as e :
        logger .warning ("Decline chat join request failed: %s",e .__class__ .__name__ )
    try :
        await _send (context .bot ,chat_id =user .id ,
        text ="Доступ к закрытому каналу открывается после оплаты 5 000 ₽. Нажмите «Оплатить 5 000 ₽».",
        reply_markup =_game10_kb_for_update (update ),
        )
    except Exception as e :
        logger .warning ("Join request notify failed: %s",e .__class__ .__name__ )


        # ============ App ============

def build_app ()->Application :
    app =Application .builder ().token (BOT_TOKEN ).build ()
    cmd =lambda handler :_guard_user_handler (handler ,busy_mode ="notify")
    cb =lambda handler :_guard_user_handler (handler ,busy_mode ="ignore")
    msg =lambda handler :_guard_user_handler (handler ,busy_mode ="notify")

    # Commands
    app .add_handler (CommandHandler ("start",cmd (start )))
    app .add_handler (CommandHandler ("menu",cmd (menu_command )))
    app .add_handler (CommandHandler ("back",cmd (menu_command )))
    app .add_handler (CommandHandler ("cancel",cmd (menu_command )))
    app .add_handler (CommandHandler ("events",cmd (show_events_command )))
    app .add_handler (CommandHandler ("courses",cmd (show_courses_command )))
    app .add_handler (CommandHandler ("catalog",cmd (show_courses_command )))
    app .add_handler (CommandHandler ("mark_paid",cmd (mark_paid_dev )))
    app .add_handler (CommandHandler ("testpay",cmd (testpay10_command )))
    app .add_handler (CommandHandler ("testpay10",cmd (testpay10_command )))
    app .add_handler (CommandHandler ("pay_debug",cmd (pay_debug )))
    app .add_handler (CommandHandler ("rag_debug",cmd (rag_debug_command )))

    # Menu callbacks
    app .add_handler (CallbackQueryHandler (cb (main_menu ),pattern ="^main_menu$"))
    app .add_handler (CallbackQueryHandler (cb (main_menu ),pattern ="^menu$"))
    app .add_handler (CallbackQueryHandler (cb (retry_db ),pattern ="^retry_db$"))

    # Sections
    app .add_handler (CallbackQueryHandler (cb (show_events ),pattern ="^events$"))
    app .add_handler (CallbackQueryHandler (cb (events_list_callback ),pattern ="^events_list$"))
    app .add_handler (CallbackQueryHandler (cb (event_list_prev ),pattern ="^event_list_prev$"))
    app .add_handler (CallbackQueryHandler (cb (event_list_next ),pattern ="^event_list_next$"))
    app .add_handler (CallbackQueryHandler (cb (event_list_refresh ),pattern ="^event_list_refresh$"))
    app .add_handler (CallbackQueryHandler (cb (event_open ),pattern ="^event_open:"))
    app .add_handler (CallbackQueryHandler (cb (show_courses ),pattern ="^courses$"))
    app .add_handler (CallbackQueryHandler (cb (show_courses_page ),pattern ="^courses_page:"))
    app .add_handler (CallbackQueryHandler (cb (show_private_channel ),pattern ="^private_channel$"))
    app .add_handler (CallbackQueryHandler (cb (show_game10_description ),pattern ="^game10_description$"))
    app .add_handler (CallbackQueryHandler (cb (private_channel_payment_info ),pattern ="^private_channel_payment_info$"))
    app .add_handler (CallbackQueryHandler (cb (game10_pay_refresh ),pattern ="^game10_pay_refresh$"))
    app .add_handler (CallbackQueryHandler (cb (game10_pay_check ),pattern ="^(?:game10_pay_check|pay_check):"))
    app .add_handler (CallbackQueryHandler (cb (pay_contact_phone ),pattern ="^pay_contact_phone$"))
    app .add_handler (CallbackQueryHandler (cb (pay_contact_email ),pattern ="^pay_contact_email$"))
    app .add_handler (CallbackQueryHandler (cb (pay_contact_cancel ),pattern ="^pay_contact_cancel$"))
    app .add_handler (CallbackQueryHandler (cb (course_link_unavailable ),pattern ="^course_link_unavailable$"))
    app .add_handler (CallbackQueryHandler (cb (show_consultations ),pattern ="^consultations$"))
    app .add_handler (CallbackQueryHandler (cb (show_formats_and_prices ),pattern ="^consult_formats$"))
    app .add_handler (CallbackQueryHandler (cb (show_ai_chat ),pattern ="^ai_chat$"))
    app .add_handler (CallbackQueryHandler (cb (show_course_questions ),pattern ="^course_questions$"))
    app .add_handler (CallbackQueryHandler (cb (game10_questions ),pattern ="^game10_questions$"))
    app .add_handler (CallbackQueryHandler (cb (event_questions ),pattern ="^event_questions:"))
    app .add_handler (CallbackQueryHandler (cb (show_contacts_request ),pattern ="^share_contacts$"))
    app .add_handler (CallbackQueryHandler (cb (contact_manager ),pattern ="^contact_manager$"))
    app .add_handler (CallbackQueryHandler (cb (show_help ),pattern ="^help$"))
    app .add_handler (CallbackQueryHandler (cb (event_register ),pattern ="^event_register:"))
    app .add_handler (CallbackQueryHandler (cb (event_cancel ),pattern ="^event_cancel:"))
    app .add_handler (CallbackQueryHandler (cb (event_pay ),pattern ="^event_pay:"))

    # Booking
    app .add_handler (CallbackQueryHandler (cb (begin_booking_individual ),pattern ="^book_individual$"))
    app .add_handler (CallbackQueryHandler (cb (begin_booking_group ),pattern ="^book_group$"))

    # Messages routing:
    app .add_handler (MessageHandler (filters .ALL ,msg (ensure_user_on_message )),group =-1 )
    app .add_handler (MessageHandler (filters .CONTACT ,msg (handle_contact_phone )),group =0 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_contact_phone_text )),group =1 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_contact_email_text )),group =2 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_navigation_text_message )),group =3 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_lead_message )),group =4 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_ai_message )),group =5 )
    app .add_handler (MessageHandler (filters .TEXT &~filters .COMMAND ,msg (handle_text_outside_assistant )),group =6 )
    app .add_handler (ChatJoinRequestHandler (handle_chat_join_request ),group =7 )

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
    logger .info ("Renata Bot started. PID=%s",os .getpid ())
    logger .warning ("Polling mode: run only ONE bot instance, otherwise Telegram getUpdates conflict may occur.")
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

