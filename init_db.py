# init_db.py
import sys
import os

# Добавляем текущую папку в путь
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Теперь можем импортировать
from sqlalchemy.ext.asyncio import create_async_engine
from models import Base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)
if os.getenv("DB_SSLMODE") == "require":
    DATABASE_URL += "?ssl=require"

engine = create_async_engine(DATABASE_URL, echo=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Все таблицы созданы")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(init_db())
    except Exception as e:
        print(f"❌ Ошибка: {e}")