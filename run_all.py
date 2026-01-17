import os
import sys
import subprocess
import multiprocessing

# Корень проекта
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def run_api():
    """Запуск FastAPI (CRM/API)"""
    os.chdir(PROJECT_ROOT)
    print("🚀 Запуск FastAPI на http://localhost:8000")
    subprocess.run(
        ["uvicorn", "core.api.api:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=PROJECT_ROOT,
        check=True
    )


def run_bot():
    """Запуск Telegram Bot"""
    os.chdir(PROJECT_ROOT)
    print("🚀 Запуск Telegram Bot")
    subprocess.run(
        [sys.executable, "-m", "telegram_bot.main"],
        cwd=PROJECT_ROOT,
        check=True
    )


def main():
    print("=" * 50)
    print("🚀 Renata Promotion - Запуск всех сервисов")
    print("=" * 50)
    print()
    
    processes = []
    
    # API процесс
    p_api = multiprocessing.Process(target=run_api, name="FastAPI")
    p_api.start()
    processes.append(p_api)
    print("✅ FastAPI запущен (PID: {})".format(p_api.pid))
    
    # Bot процесс
    p_bot = multiprocessing.Process(target=run_bot, name="TelegramBot")
    p_bot.start()
    processes.append(p_bot)
    print("✅ Telegram Bot запущен (PID: {})".format(p_bot.pid))
    
    print()
    print("=" * 50)
    print("📋 Запущенные процессы:")
    print("-" * 50)
    for p in processes:
        print(f"   • {p.name} (PID: {p.pid})")
    print("-" * 50)
    print()
    print("🌐 FastAPI docs: http://localhost:8000/docs")
    print("🌐 ReDoc: http://localhost:8000/redoc")
    print("🛑 Нажми Ctrl+C для остановки")
    print("=" * 50)
    print()
    
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print()
        print("🛑 Остановка всех сервисов...")
        for p in processes:
            p.terminate()
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
        print("✅ Все сервисы остановлены")


if __name__ == "__main__":
    main()