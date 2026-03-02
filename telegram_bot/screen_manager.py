from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden, TimedOut

from telegram_bot.text_utils import normalize_telegram_text, normalize_text_for_telegram, normalize_ui_reply_markup

logger = logging.getLogger(__name__)


class ScreenManager:
    UI_ANCHOR_MESSAGE_ID_KEY = "ui_anchor_message_id"
    MENU_ANCHOR_MESSAGE_ID_KEY = "menu_anchor_message_id"
    # Legacy alias kept for compatibility with existing tests/contexts.
    LAST_SCREEN_MESSAGE_ID_KEY = UI_ANCHOR_MESSAGE_ID_KEY

    @staticmethod
    def _can_edit_message_with_markup(reply_markup) -> bool:
        return reply_markup is None or isinstance(reply_markup, InlineKeyboardMarkup)

    def clear_screen(self, context) -> None:
        if context is None:
            return
        try:
            context.user_data.pop(self.UI_ANCHOR_MESSAGE_ID_KEY, None)
            context.user_data.pop("last_screen_message_id", None)
        except Exception:
            pass

    def _get_anchor_message_id(self, context):
        if context is None:
            return None
        data = getattr(context, "user_data", None) or {}
        return (
            data.get(self.UI_ANCHOR_MESSAGE_ID_KEY)
            or data.get(self.MENU_ANCHOR_MESSAGE_ID_KEY)
            or data.get("last_screen_message_id")
        )

    def _get_menu_anchor_message_id(self, context):
        if context is None:
            return None
        data = getattr(context, "user_data", None) or {}
        return data.get(self.MENU_ANCHOR_MESSAGE_ID_KEY)

    def _set_anchor_message_id(self, context, message_id) -> None:
        if context is None:
            return
        try:
            context.user_data[self.UI_ANCHOR_MESSAGE_ID_KEY] = message_id
        except Exception:
            pass

    def _set_menu_anchor_message_id(self, context, message_id) -> None:
        if context is None:
            return
        try:
            context.user_data[self.MENU_ANCHOR_MESSAGE_ID_KEY] = message_id
        except Exception:
            pass

    def _build_edit_candidates(self, *, callback_query, anchor_message_id):
        candidates: list[int] = []
        if anchor_message_id:
            candidates.append(anchor_message_id)
        callback_message = getattr(callback_query, "message", None)
        callback_message_id = getattr(callback_message, "message_id", None)
        if callback_message_id and callback_message_id not in candidates:
            candidates.append(callback_message_id)
        return candidates

    async def show_screen(
        self,
        update: Update,
        context,
        text: str | None,
        reply_markup=None,
        parse_mode: str | None = None,
        prefer_new_on_message: bool = False,
        ui_mode: bool = True,
        **kwargs,
    ):
        if context is None or getattr(context, "bot", None) is None:
            return None
        chat = getattr(update, "effective_chat", None)
        if chat is None or getattr(chat, "id", None) is None:
            return None

        chat_id = chat.id
        normalized_text = normalize_telegram_text(
            normalize_text_for_telegram(text, label="screen")
        ) or ""
        normalized_reply_markup = normalize_ui_reply_markup(reply_markup)
        anchor_message_id = self._get_anchor_message_id(context)
        is_message_update = getattr(update, "message", None) is not None
        callback_query = getattr(update, "callback_query", None)

        if callback_query is not None:
            try:
                await callback_query.answer()
            except Exception:
                pass

        if not ui_mode:
            try:
                sent = await context.bot.send_message(
                    chat_id=chat_id,
                    text=normalized_text,
                    reply_markup=normalized_reply_markup,
                    parse_mode=parse_mode,
                    **kwargs,
                )
            except TimedOut as exc:
                logger.warning("NET issue [screen_send_message]: %s", exc.__class__.__name__)
                await self._notify_timeout_best_effort(callback_query)
                return None
            return sent

        should_try_edit = (
            self._can_edit_message_with_markup(normalized_reply_markup)
            and (
                callback_query is not None
                or (is_message_update and anchor_message_id and not prefer_new_on_message)
            )
        )
        if should_try_edit:
            for target_message_id in self._build_edit_candidates(
                callback_query=callback_query,
                anchor_message_id=anchor_message_id,
            ):
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=target_message_id,
                        text=normalized_text,
                        reply_markup=normalized_reply_markup,
                        parse_mode=parse_mode,
                        **kwargs,
                    )
                    self._set_anchor_message_id(context, target_message_id)
                    return None
                except TimedOut as exc:
                    logger.warning("NET issue [screen_edit_message]: %s", exc.__class__.__name__)
                    break
                except BadRequest as e:
                    message = (str(e) or "").lower()
                    if "message is not modified" in message:
                        self._set_anchor_message_id(context, target_message_id)
                        return None
                    recoverable = (
                        "message to edit not found",
                        "message can't be edited",
                        "message_id_invalid",
                        "there is no text in the message to edit",
                    )
                    if not any(item in message for item in recoverable):
                        raise
                except Exception:
                    # Fallback to send_message on any edit-related issue.
                    break

        try:
            sent = await context.bot.send_message(
                chat_id=chat_id,
                text=normalized_text,
                reply_markup=normalized_reply_markup,
                parse_mode=parse_mode,
                **kwargs,
            )
        except TimedOut as exc:
            logger.warning("NET issue [screen_send_message_fallback]: %s", exc.__class__.__name__)
            await self._notify_timeout_best_effort(callback_query)
            return None
        await self._delete_old_screen_best_effort(
            context,
            chat_id=chat_id,
            old_message_id=anchor_message_id,
            new_message_id=sent.message_id,
        )
        self._set_anchor_message_id(context, sent.message_id)
        return sent

    async def show_main_menu_bottom(
        self,
        update: Update,
        context,
        text: str | None,
        reply_markup=None,
        parse_mode: str | None = None,
        **kwargs,
    ):
        if context is None or getattr(context, "bot", None) is None:
            return None
        chat = getattr(update, "effective_chat", None)
        if chat is None or getattr(chat, "id", None) is None:
            return None

        callback_query = getattr(update, "callback_query", None)
        if callback_query is not None:
            try:
                await callback_query.answer()
            except Exception:
                pass

        normalized_text = normalize_telegram_text(
            normalize_text_for_telegram(text, label="menu_bottom")
        ) or ""
        normalized_reply_markup = normalize_ui_reply_markup(reply_markup)

        try:
            sent = await context.bot.send_message(
                chat_id=chat.id,
                text=normalized_text,
                reply_markup=normalized_reply_markup,
                parse_mode=None,
                **kwargs,
            )
        except TimedOut as exc:
            logger.warning("NET issue [menu_bottom_send_message]: %s", exc.__class__.__name__)
            await self._notify_timeout_best_effort(callback_query)
            return None

        self._set_menu_anchor_message_id(context, sent.message_id)
        self._set_anchor_message_id(context, sent.message_id)
        return sent

    async def update_main_menu_anchor(
        self,
        update: Update,
        context,
        text: str | None,
        reply_markup=None,
        parse_mode: str | None = None,
        **kwargs,
    ):
        if context is None or getattr(context, "bot", None) is None:
            return None
        chat = getattr(update, "effective_chat", None)
        if chat is None or getattr(chat, "id", None) is None:
            return None

        callback_query = getattr(update, "callback_query", None)
        if callback_query is not None:
            try:
                await callback_query.answer()
            except Exception:
                pass

        normalized_text = normalize_telegram_text(
            normalize_text_for_telegram(text, label="menu_anchor")
        ) or ""
        normalized_reply_markup = normalize_ui_reply_markup(reply_markup)
        menu_anchor_message_id = self._get_menu_anchor_message_id(context)

        if menu_anchor_message_id and self._can_edit_message_with_markup(normalized_reply_markup):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=menu_anchor_message_id,
                    text=normalized_text,
                    reply_markup=normalized_reply_markup,
                    parse_mode=None,
                    **kwargs,
                )
                self._set_menu_anchor_message_id(context, menu_anchor_message_id)
                self._set_anchor_message_id(context, menu_anchor_message_id)
                return None
            except TimedOut as exc:
                logger.warning("NET issue [menu_anchor_edit_message]: %s", exc.__class__.__name__)
            except BadRequest as e:
                message = (str(e) or "").lower()
                if "message is not modified" in message:
                    self._set_menu_anchor_message_id(context, menu_anchor_message_id)
                    self._set_anchor_message_id(context, menu_anchor_message_id)
                    return None
                recoverable = (
                    "message to edit not found",
                    "message can't be edited",
                    "message_id_invalid",
                    "there is no text in the message to edit",
                )
                if not any(item in message for item in recoverable):
                    raise
            except Exception:
                pass

        try:
            sent = await context.bot.send_message(
                chat_id=chat.id,
                text=normalized_text,
                reply_markup=normalized_reply_markup,
                parse_mode=None,
                **kwargs,
            )
        except TimedOut as exc:
            logger.warning("NET issue [menu_anchor_send_message]: %s", exc.__class__.__name__)
            await self._notify_timeout_best_effort(callback_query)
            return None
        self._set_menu_anchor_message_id(context, sent.message_id)
        self._set_anchor_message_id(context, sent.message_id)
        return sent

    async def _notify_timeout_best_effort(self, callback_query) -> None:
        if callback_query is None:
            return
        try:
            await callback_query.answer("Telegram временно не отвечает, попробуйте ещё раз.")
        except Exception:
            pass

    async def _delete_old_screen_best_effort(self, context, *, chat_id: int, old_message_id, new_message_id: int) -> None:
        if context is None or getattr(context, "bot", None) is None:
            return
        if not old_message_id:
            return
        try:
            if int(old_message_id) == int(new_message_id):
                return
        except Exception:
            pass
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
        except (BadRequest, Forbidden):
            pass
        except Exception:
            pass
