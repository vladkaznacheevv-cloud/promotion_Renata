import os
import sys
import subprocess
import multiprocessing

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ВАЖНО: для Windows spawn прокидываем PYTHONPATH вручную
ENV = os.environ.copy()
ENV["PYTHONPATH"] = PROJECT_ROOT

def run_api():
    print("🚀 Запуск FastAPI на http://localhost:8000")
    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "core.api.api:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000",
        ],
        cwd=PROJECT_ROOT,
        env=ENV,
        check=True,
    )

def run_bot():
    print("🚀 Запуск Telegram Bot")
    subprocess.run(
        [sys.executable, "-m", "telegram_bot.main"],
        cwd=PROJECT_ROOT,
        env=ENV,
        check=True,
    )

def main():
    print("=" * 50)
    print("🚀 Renata Promotion - Запуск всех сервисов")
    print("=" * 50)

    processes = [
        multiprocessing.Process(target=run_api, name="FastAPI"),
        multiprocessing.Process(target=run_bot, name="TelegramBot"),
    ]

    for p in processes:
        p.start()
        print(f"✅ {p.name} запущен (PID: {p.pid})")

    print("\n🌐 FastAPI docs: http://localhost:8000/docs")
    print("🌐 ReDoc: http://localhost:8000/redoc")
    print("🛑 Нажми Ctrl+C для остановки\n")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n🛑 Остановка всех сервисов...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
        print("✅ Все сервисы остановлены")

if __name__ == "__main__":
    main()
