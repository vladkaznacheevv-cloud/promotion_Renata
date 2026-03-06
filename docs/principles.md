# principles.md

## 1. Главный принцип

Проект развивается по принципу:

**минимальные изменения, предсказуемый runtime, явные границы ответственности.**

---

## 2. Архитектурные принципы

### 2.1 Core-first
Любая бизнес-логика по возможности должна жить в `core/`.

### 2.2 Outside -> Core dependency direction
Разрешённое направление зависимостей:

- frontend -> core
- bot -> core
- integrations -> core

### 2.3 Thin clients
Bot и CRM frontend — тонкие клиенты.
Они отображают данные и вызывают API/сервисы, но не дублируют доменные правила.

### 2.4 Explicit integrations
Внешние сервисы должны быть изолированы:
- отдельные модули;
- отдельные конфиги/env;
- безопасные ошибки;
- без утечки секретов в логах.

### 2.5 Environment-safe execution
Никакой `sys.path`-магии, хардкода путей и неявного поведения окружения.

---

## 3. Принципы безопасности

### 3.1 Не раскрывать секреты
Никогда не печатать:
- `BOT_TOKEN`
- `JWT_SECRET`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MANAGEMENT_KEY`
- `DATABASE_URL`
- webhook tokens
- invite links
- PII

### 3.2 Безопасные ошибки
Ошибки должны быть:
- читаемыми;
- короткими;
- полезными;
- без секретов.

### 3.3 Минимально достаточные права
Нельзя размывать CRM allowlist, auth guard и admin-флоу без причины.

---

## 4. Принципы изменений в коде

### 4.1 Минимальные правки
Если задачу можно решить локально, не нужен большой рефакторинг.

### 4.2 Не ломать контракты
Если меняется:
- API response/request;
- env имя;
- compose сервис;
- database schema;
- UI поток в боте;

то это нужно явно объяснить.

### 4.3 Обратимость
Предпочтение:
- additive migrations;
- новые поля вместо ломки старых путей;
- feature flag, если уместно.

### 4.4 UTF-8 everywhere
Все тексты, кнопки, markdown-файлы и исходники — в UTF-8.

---

## 5. Принципы по данным и интеграциям

### 5.1 Source of truth
- доменная логика — в `core/`;
- runtime-поведение — в коде;
- docs отражают код, а не подменяют его.

### 5.2 Webhook-first
Для GetCourse закреплён путь `webhook-only`.

### 5.3 AI не заменяет факты
AI-ответы не должны подменять:
- реальные события;
- платежные статусы;
- CRM-данные;
- RAG-факты.

### 5.4 RAG как контролируемый контекст
`rag_data/` и `core/rag/` должны оставаться прозрачной частью системы.

---

## 6. Принципы проверки

### Backend
python -m compileall core
uvicorn core.main:app --port 8000
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz

### Bot
python -m telegram_bot.health
python telegram_bot/main.py

### Frontend
cd crm_web/admin-panel
npm ci
npm run build

### AI / RAG
python scripts/smoke_openrouter.py
python scripts/rag_smoke.py "курс getcourse"