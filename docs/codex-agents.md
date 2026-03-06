# codex-agents.md

## 1. Зачем разбивать CODEX на агентов

Проект уже достаточно большой:
- backend;
- Telegram bot;
- CRM frontend;
- AI/RAG;
- платежи;
- webhook-интеграции;
- infra/deploy.

Один универсальный агент слишком быстро начинает смешивать слои.
Поэтому правильнее делить задачи по ролям.

---

## 2. Правила координации агентов

### 2.1 Кто главный
Главный агент по умолчанию — **Architecture Guard**.

### 2.2 Как передавать задачу
- API / DB / auth / webhooks -> Backend/API Agent
- UX Telegram / handlers / keyboards -> Telegram Bot Agent
- CRM UI / таблицы / фильтры / страницы -> CRM Frontend Agent
- OpenRouter / RAG / retrieval -> AI/RAG Agent
- compose / nginx / deploy / health / scripts -> Infra/Deploy Agent
- build / smoke / regression -> QA/Smoke Agent

### 2.3 Когда нужны два агента
Примеры:
- payment flow -> Backend/API Agent + Telegram Bot Agent
- CRM график по AI -> Backend/API Agent + CRM Frontend Agent
- RAG endpoint -> AI/RAG Agent + Backend/API Agent
- deploy issue -> Infra/Deploy Agent + QA/Smoke Agent

---

## 3. Состав агентов

## Agent 1 — Architecture Guard
### Зона ответственности
- `agents.md`
- `docs/architecture.md`
- `docs/principles.md`

### Что делает
- проверяет границы слоёв;
- не даёт тащить логику в UI;
- валидирует соответствие текущей архитектуре.

---

## Agent 2 — Backend/API Agent
### Зона ответственности
- `core/main.py`
- `core/api/*`
- `core/crm/*`
- `core/auth/*`
- `core/models.py`
- `core/users/*`

### Что делает
- FastAPI endpoints;
- auth/JWT/allowlist;
- webhook’и GetCourse/YooKassa;
- CRM API;
- сервисная логика в `core/`.

---

## Agent 3 — Telegram Bot Agent
### Зона ответственности
- `telegram_bot/main.py`
- `telegram_bot/handlers/*`
- `telegram_bot/keyboards/*`
- `telegram_bot/text_utils.py`

### Что делает
- меню, навигация, callback flows;
- assistant mode;
- payment UX в Telegram;
- UTF-8 и читаемость текстов.

---

## Agent 4 — CRM Frontend Agent
### Зона ответственности
- `crm_web/admin-panel/src/pages/*`
- `crm_web/admin-panel/src/components/*`
- `crm_web/admin-panel/src/api/*`
- `crm_web/admin-panel/src/layout/*`
- `crm_web/admin-panel/src/i18n/*`

### Что делает
- страницы CRM;
- таблицы, фильтры, модалки;
- визуализация AI/OpenRouter данных;
- Vite build.

---

## Agent 5 — AI/RAG Agent
### Зона ответственности
- `core/ai/*`
- `core/rag/*`
- `rag_data/*`

### Что делает
- OpenRouter вызовы;
- retrieval pipeline;
- контроль `events -> RAG -> model`;
- knowledge files.

---

## Agent 6 — Infra/Deploy Agent
### Зона ответственности
- `compose.prod.yml`
- Dockerfile’ы
- nginx config
- `scripts/*`

### Что делает
- продовый runtime;
- healthchecks;
- deploy scripts;
- loopback/proxy/ports.

---

## Agent 7 — QA/Smoke Agent
### Зона ответственности
- smoke scripts
- build checks
- regression checks

### Что делает
- проверяет, что изменения реально работают;
- не делает широких рефакторингов.

---

## 4. Маршрутизация типовых задач

### Если сломалась оплата и пользователь не получил доступ
1. Backend/API Agent
2. Telegram Bot Agent
3. QA/Smoke Agent

### Если нужно переработать экран клиентов в CRM
1. CRM Frontend Agent
2. Backend/API Agent — если нужен новый API
3. QA/Smoke Agent

### Если AI отвечает не по базе знаний
1. AI/RAG Agent
2. Backend/API Agent — если нужен endpoint
3. QA/Smoke Agent

### Если frontend unhealthy
1. Infra/Deploy Agent
2. QA/Smoke Agent

### Если задача спорная и межслойная
1. Architecture Guard
2. профильный агент
3. QA/Smoke Agent

---

## 5. Формат постановки задачи агенту

Роль: <имя агента>

Контекст:
- проект promotion_Renata
- минимальные правки
- не ломать API/compose
- не логировать секреты/PII/invite links
- UTF-8 обязателен

Задача:
<что нужно сделать>

Обязательные проверки:
- <команды>

Финальный ответ:
- findings
- changed files
- verification steps
- residual risks