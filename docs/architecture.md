# architecture.md

## 1. Назначение проекта

`promotion_Renata` — это проект CRM-системы, Telegram-бота и AI-ассистента для психолога Ренаты.

Система нужна для:
- приёма и сопровождения клиентов;
- CRM-учёта клиентов, оплат и событий;
- работы Telegram-бота как точки входа;
- ответов AI-ассистента через OpenRouter + локальный RAG;
- обработки webhook’ов от внешних систем.

---

## 2. Актуальная архитектурная схема

[Telegram User]
↕ Telegram API
[telegram_bot]
↕ HTTP / internal service calls
[FastAPI backend: core/main.py]
↕ SQLAlchemy
[PostgreSQL external]

[CRM Frontend: crm_web/admin-panel]
↕ HTTP API
[FastAPI backend]

[GetCourse webhook-only]
-> /api/webhooks/getcourse

[YooKassa webhooks / payments]
-> /api/webhooks/yookassa/...

[OpenRouter]
↔ core/ai/*

[Local RAG data]
↔ core/rag/* + rag_data/*.md

---

## 3. Слои проекта

### 3.1 Core domain layer — `core/`
Главный слой проекта.

Здесь должны находиться:
- бизнес-логика;
- модели SQLAlchemy;
- сервисы;
- orchestration AI/RAG;
- CRM API и auth;
- логика обработки webhook’ов и платежных сценариев.

### 3.2 Telegram Bot layer — `telegram_bot/`
Тонкий слой взаимодействия с пользователем в Telegram.

Здесь должно быть:
- handlers;
- keyboards;
- screen/navigation logic;
- polling runtime;
- вызовы backend/core сервисов.

### 3.3 CRM / API layer — `crm_web/admin-panel/` + backend в `core/*`
Состоит из двух частей:

1. Frontend (`crm_web/admin-panel/`)
   - React/Vite UI;
   - таблицы, фильтры, формы, графики;
   - presentation + вызовы API.

2. Backend API (`core/...`)
   - FastAPI endpoints;
   - auth/JWT;
   - CRM endpoints;
   - AI stats / integrations / payments / webhook routes.

### 3.4 Integrations layer
Внешние системы:
- GetCourse (`webhook-only`);
- YooKassa;
- OpenRouter;
- будущие провайдеры оплат и сервисы.

### 3.5 Infra/runtime layer
Ключевые элементы:
- `compose.prod.yml`;
- сервисы `web`, `bot`, `frontend`, `migrate`;
- внешний PostgreSQL;
- nginx / reverse proxy;
- env-конфигурация;
- health endpoints `/healthz` и `/readyz`;
- deploy scripts / smoke scripts в `scripts/`.

---

## 4. Entrypoints

### Backend
- `core/main.py`

### Telegram Bot
- `telegram_bot/main.py`
- `python -m telegram_bot.health`

### Frontend CRM
- `crm_web/admin-panel`

### Compose / migration
- `compose.prod.yml`
- `scripts/*`

---

## 5. Подтверждённые архитектурные решения

### 5.1 Core-first
Bot и CRM являются клиентами `core`, а не самостоятельными центрами бизнес-логики.

### 5.2 GetCourse webhook-only
Проект отказался от Export API.
Рабочий путь: принимать webhook’и, хранить события, показывать summary/events в CRM.

### 5.3 AI pipeline
Приоритет ответа:
`events -> RAG -> model`

### 5.4 PostgreSQL вне compose
База данных вынесена отдельно от prod-compose runtime.

### 5.5 Thin runtime clients
- Telegram bot — thin interaction layer
- CRM frontend — thin presentation layer
- ключевая логика должна жить в backend/core