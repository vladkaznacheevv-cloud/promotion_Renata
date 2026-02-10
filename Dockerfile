FROM python:3.11-slim

# отключаем лишний вывод
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# рабочая директория
WORKDIR /app

# системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# зависимости Python
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# код проекта
COPY . .

# команда по умолчанию (может быть переопределена в docker-compose)
CMD ["python", "-m", "telegram_bot.main"]

