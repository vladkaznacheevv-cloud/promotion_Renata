import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from core.database import AsyncSessionLocal
from core.models import User
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная BOT_TOKEN не найдена в .env")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or None
    username = update.effective_user.username

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        existing = result.scalars().first()

        if not existing:
            new_user = User(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username
            )
            session.add(new_user)
            await session.commit()
            await update.message.reply_text("✅ Ты добавлен в базу!")
        else:
            await update.message.reply_text("👋 С возвращением!")

if __name__ == "__main__":
    import asyncio

    async def run_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))

        async with app:
            await app.start()
            await app.updater.start_polling()
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                await app.updater.stop()
                await app.stop()

    asyncio.run(run_bot())