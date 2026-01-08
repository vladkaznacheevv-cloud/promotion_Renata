import sys
import os

project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

from shared.database import get_engine
from sqlalchemy import text

try:
    engine = get_engine()
    print("📡 Подключаюсь к Timeweb Cloud PostgreSQL...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print(" Успешно!")
        print(" Версия:", result.fetchone()[0])
except Exception as e:
    print(" Ошибка подключения:")
    print(e)