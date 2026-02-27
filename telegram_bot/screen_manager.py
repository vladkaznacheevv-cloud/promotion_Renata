from __future__ import annotations

from telegram import Update
from telegram.error import BadRequest

from telegram_bot.text_utils import normalize_telegram_text, normalize_text_for_telegram, normalize_ui_reply_markup


class ScreenManager:
    LAST_SCREEN_MESSAGE_ID_KEY = "last_screen_message_id"

    def clear_screen(self, context) -> None:
        if context is None:
            return
        try:
            context.user_data.pop(self.LAST_SCREEN_MESSAGE_ID_KEY, None)
        except Exception:
            pass

    async def show_screen(
        self,
        update: Update,
        context,
        text: str | None,
        reply_markup=None,
        parse_mode: str | None = None,
        prefer_new_on_message: bool = True,
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
        last_message_id = context.user_data.get(self.LAST_SCREEN_MESSAGE_ID_KEY)
        is_message_update = getattr(update, "message", None) is not None

        if prefer_new_on_message and is_message_update:
            sent = await context.bot.send_message(
                chat_id=chat_id,
                text=normalized_text,
                reply_markup=normalized_reply_markup,
                parse_mode=parse_mode,
                **kwargs,
            )
            await self._delete_old_screen_best_effort(context, chat_id=chat_id, old_message_id=last_message_id, new_message_id=sent.message_id)
            try:
                context.user_data[self.LAST_SCREEN_MESSAGE_ID_KEY] = sent.message_id
            except Exception:
                pass
            return sent

        if last_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_message_id,
                    text=normalized_text,
                    reply_markup=normalized_reply_markup,
                    parse_mode=parse_mode,
                    **kwargs,
                )
                return None
            except BadRequest as e:
                message = (str(e) or "").lower()
                if "message is not modified" in message:
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
                pass

        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=normalized_text,
            reply_markup=normalized_reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
        await self._delete_old_screen_best_effort(context, chat_id=chat_id, old_message_id=last_message_id, new_message_id=sent.message_id)
        try:
            context.user_data[self.LAST_SCREEN_MESSAGE_ID_KEY] = sent.message_id
        except Exception:
            pass
        return sent

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
        except Exception:
            pass
