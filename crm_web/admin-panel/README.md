# Admin Panel

## Backend (FastAPI)

From repo root:

```bash
uvicorn core.main:app --reload --host 127.0.0.1 --port 8000
```

Health: http://127.0.0.1:8000/health
Docs: http://127.0.0.1:8000/docs

---

## Auth (CRM)

Создай администратора (из корня репозитория):

```bash
set ADMIN_EMAIL=admin@example.com
set ADMIN_PASSWORD=changeme
set ADMIN_ROLE=admin
python scripts/create_admin_user.py
```

Токен хранится в localStorage, авторизация через Bearer JWT.

# Telegram Bot (Polling)

From repo root:

```bash
python telegram_bot/main.py
```

Polling mode: запускай только один экземпляр бота (иначе Telegram вернёт Conflict).

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.


## Run Backend + Frontend (Dev)

From repo root:

```bash
# Backend
uvicorn core.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Frontend
cd crm_web/admin-panel
npm run dev -- --host 127.0.0.1
```

Health: http://127.0.0.1:8000/health
Docs: http://127.0.0.1:8000/docs
Frontend: http://127.0.0.1:5173



## CRM dev seed

From repo root (after configuring DB env vars):

```bash
python scripts/seed_crm.py
```

This creates tables (if missing) and inserts 2 demo clients + 2 events when the DB is empty.

## Manual checklist (Bot → DB → CRM)

1) Запусти backend: `uvicorn core.main:app --reload --host 127.0.0.1 --port 8000`
2) Запусти бота: `python telegram_bot/main.py`
3) Напиши боту `/start` и любое сообщение
4) Проверь, что пользователь появился/обновился:
   - API: `http://127.0.0.1:8000/api/crm/clients`
   - CRM UI: `http://127.0.0.1:5173`


## E2E smoke checklist (CRM events)

1. Авторизуйтесь под `admin` или `manager`.
2. Откройте `/events`.
3. Нажмите `Добавить мероприятие`.
4. Заполните обязательные поля: `Название`, `Описание`, `Дата`.
5. Нажмите `Сохранить`.
6. Убедитесь, что запись появилась в таблице мероприятий.
7. Нажмите `Изменить` у созданного мероприятия.
8. Измените `Название` и `Описание`, затем нажмите `Сохранить`.
9. Убедитесь, что изменения отобразились в таблице и в карточке мероприятия.
10. Откройте DevTools -> `Network` и проверьте:
11. `POST /api/crm/events` возвращает `200` и JSON-объект созданного мероприятия.
12. `PATCH /api/crm/events/{id}` возвращает `200` и JSON-объект обновленного мероприятия.

Дополнительно:
- Быстрое действие `Добавить клиента` ведет на `/clients?create=1` и открывает модалку клиента.
- Быстрое действие `Создать мероприятие` ведет на `/events?create=1` и открывает модалку мероприятия.
- Для роли `viewer` кнопки создания/редактирования скрыты.
