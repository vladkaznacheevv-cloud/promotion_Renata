import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from models import User, Base
from database import async_session, engine
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная BOT_TOKEN не найдена в .env")

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Таблицы созданы при запуске бота")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔄 Получена команда /start от {update.effective_user.id}")
    try:
        async with async_session() as session:
            user_id = update.effective_user.id
            first_name = update.effective_user.first_name or ""
            last_name = update.effective_user.last_name
            username = update.effective_user.username

            print(f"🔍 Ищу пользователя {user_id}...")
            existing = await session.get(User, user_id)
            if not existing:
                print(f"🆕 Добавляю нового пользователя {user_id}")
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
                print(f"👋 Пользователь {user_id} уже существует")
                await update.message.reply_text("👋 С возвращением!")
    except Exception as e:
        print(f"❌ Ошибка при сохранении пользователя: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

if __name__ == "__main__":
    import asyncio
    
    async def run_bot():
        await create_tables()
        
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        print("🚀 Бот запущен...")
        
        # Используй async with
        async with app:
            await app.start()
            await app.updater.start_polling()
            
            # Ждём завершения
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Бот остановлен")
            finally:
                await app.updater.stop()
                await app.stop()

    asyncio.run(run_bot())