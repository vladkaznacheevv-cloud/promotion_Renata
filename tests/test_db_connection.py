import sys
import os

# Добавляем корень проекта в путь
project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# загружаем .env
from dotenv import load_dotenv
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

# импортируем функцию из shared
from shared.database import get_engine
from sqlalchemy import text

try:
    engine = get_engine()
    print("📡 Подключаюсь к PostgreSQL...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print("✅ Успешно подключён!")
        print("📦 Версия БД:", result.fetchone()[0])
except Exception as e:
    print("❌ Ошибка:")
    print(e)