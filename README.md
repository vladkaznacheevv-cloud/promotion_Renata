# promotion_Renata

## Запуск Docker-стека

```bash
docker-compose up -d --build
docker-compose ps
```

Сервисы:
- `frontend`: `http://localhost`
- `backend`: `http://localhost:8000/docs`
- `crm ping`: `http://localhost/api/crm/ping`

### External DB по умолчанию

`docker-compose.yml` рассчитан на внешнюю БД (remote `DATABASE_URL` / `DB_*`).
В нём нет `db` и `getcourse_cron`.

Локальная разработка с встроенным Postgres и cron:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

## Bot Polling: только один экземпляр

Бот работает в polling (`getUpdates`) и должен быть запущен только в одном экземпляре.

Что добавлено:
- lock-файл: `/tmp/renata_bot.lock`
- lock-путь можно переопределить через `BOT_LOCK_PATH`
- лог инстанса: `host`, `pid`, `token_hash` (без вывода токена)
- при занятом lock второй процесс завершается, не создавая конфликтов

Проверка:

```bash
docker-compose logs -f bot
```

В логах должны быть строки:
- `Bot instance metadata: host=... pid=... token_hash=...`
- `Renata Bot запущен...`

Если видите `Telegram polling conflict`, проверьте лишние процессы:

```bash
docker-compose ps
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -i bot
```

Как найти второй экземпляр бота (гарантированный чек):

- Windows:
```powershell
docker ps | findstr bot
```
- Linux/macOS:
```bash
docker ps | grep bot
```

Проверка на второй compose-project (другой каталог/другой `docker-compose.yml`):

```bash
docker ps --format "{{.Names}}\t{{.Image}}\t{{.Labels}}"
```

Чеклист:
- убедиться, что запущен только один контейнер `bot`
- убедиться, что локально не запущен `python -m telegram_bot.main`
- убедиться, что `BOT_LOCK_PATH` указывает в доступный путь внутри контейнера

### Bot unhealthy

Healthcheck бота выполняет `python -m telegram_bot.health` (проверка импортов и `SELECT 1` в DB, без Telegram API).

Проверка health-логов:

```bash
docker inspect --format='{{range .State.Health.Log}}{{println .End " exit=" .ExitCode " output=" .Output}}{{end}}' project_root_bot_1
```

## GetCourse (MVP)

С февраля 2026 интеграция работает в webhook-режиме. Экспорт через `/pl/api/account/*` отключён в runtime (sync endpoint не запускает export/poll).

ENV:
- `GETCOURSE_ENABLED`
- `GETCOURSE_EXPORT_ENABLED=false` (по умолчанию, export runtime выключен)
- `GETCOURSE_BASE_URL`
- `GETCOURSE_WEBHOOK_TOKEN`
- `GETCOURSE_API_KEY` (опционально; в summary показывается только как индикатор `has_key`)

### GetCourse env в docker-compose

Если интеграция не активна, проверьте `.env` и перезапустите `web`:

```bash
docker-compose up -d --build web
```

`GETCOURSE_BASE_URL` должен быть только origin (домен), без пути и query:
- правильно: `https://renataminakova.getcourse.ru`
- неправильно: `https://renataminakova.getcourse.ru/pl/cms/page/view?id=...`

Webhook-режим:
- `POST /api/webhooks/getcourse` принимает события от GetCourse и сохраняет их в БД;
- `GET /api/crm/integrations/getcourse/summary` показывает состояние подключения и счётчики событий;
- `GET /api/crm/integrations/getcourse/events` возвращает последние webhook-события;
- `POST /api/crm/integrations/getcourse/sync` больше не запускает export/poll и используется как безопасный refresh summary.

Проверка summary:

```bash
curl -i http://localhost/api/crm/integrations/getcourse/summary -H "Authorization: Bearer <TOKEN>"
```

Проверка событий:

```bash
curl -i "http://localhost/api/crm/integrations/getcourse/events?limit=50" -H "Authorization: Bearer <TOKEN>"
```

Проверка webhook:

```bash
curl -i -X POST "http://localhost:8000/api/webhooks/getcourse" \
  -H "X-Webhook-Token: $GETCOURSE_WEBHOOK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_id":"evt-1","event_type":"payment","user_email":"test@example.com","deal_number":"D-1","amount":100,"currency":"RUB","status":"paid"}'
```

Проверка ping (admin):

```bash
curl -i http://localhost/api/crm/integrations/getcourse/ping -H "Authorization: Bearer <TOKEN>"
```

Диагностика (admin):

```bash
curl -i http://localhost/api/crm/integrations/getcourse/diagnose -H "Authorization: Bearer <TOKEN>"
```

Refresh summary (admin):

```bash
curl -i -X POST "http://localhost/api/crm/integrations/getcourse/sync" -H "Authorization: Bearer <TOKEN>"
```

Пример ответа `summary`:

```json
{
  "enabled": true,
  "has_key": true,
  "base_url": "https://renataminakova.getcourse.ru",
  "status": "OK",
  "last_sync_at": "2026-02-14T04:45:00+00:00",
  "last_event_at": "2026-02-14T04:44:10+00:00",
  "events_last_24h": 5,
  "events_last_7d": 19,
  "lastError": null,
  "counts": {
    "events": 19,
    "fetched": 5
  }
}
```

### Бэкап IntegrationState

Перед изменениями интеграции сохраните снимок состояния:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec db \
  sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "COPY (SELECT id,name,last_sync_at,last_error,updated_at,payload_json FROM integration_state ORDER BY id) TO STDOUT WITH CSV HEADER"' \
  > integration_state_backup.csv
```

Проверка импорта в CRM:
- откройте `http://localhost` -> `Интеграции` -> `Синхронизировать`;
- откройте `Мероприятия` и проверьте, что появились/обновились события с `link_getcourse`;
- откройте `Каталог` и проверьте, что появились позиции без дат;
- повторите sync и убедитесь, что количество событий не растёт без новых сущностей в GetCourse.

Проверка API каталога:

```bash
curl -i "http://localhost/api/crm/catalog?limit=20&offset=0" -H "Authorization: Bearer <TOKEN>"
```

Проверка бота:
- у события должен быть заполнен `link_getcourse`
- в `/events` у карточки появится кнопка `Открыть на GetCourse`
- в `/courses` выводятся позиции из `catalog_items` с кнопкой `Перейти на GetCourse`

## Исправление mojibake в БД (события)

Если в таблице `events` уже лежат «кракозябры» (`Рџ...`, `рџ...`), используйте fixer.

Dry-run (по умолчанию):

```bash
docker-compose exec web python scripts/fix_mojibake.py
```

Применить изменения:

```bash
docker-compose exec web python scripts/fix_mojibake.py --apply
```

Ограничить проверку (диагностика):

```bash
docker-compose exec web python scripts/fix_mojibake.py --limit 50
```

Fixer меняет только `events.title`, `events.description`, `events.location` и только если:
- строка похожа на mojibake,
- восстановленная строка содержит кириллицу,
- в результате нет маркеров mojibake.

## Тесты

```bash
pytest -q -p no:cacheprovider
```

Frontend build + smoke:

```bash
cd crm_web/admin-panel
npm run build
npm run smoke:mvp
npm run smoke:integrations
npm run smoke:catalog
npm run smoke:dropdown
```

Добавлены тесты:
- форматирование карточки события (кириллица + эвристика mojibake)
- smoke UTF-8 roundtrip
- repair mojibake (`РџСЂРёРІРµС‚` -> `Привет`)
- lock path + single-instance lock
- контракт GetCourse summary/sync

## Дополнительно по миграциям

```bash
docker-compose exec web python scripts/migrate_payments_mvp.py
docker-compose exec web python scripts/migrate_funnel_contacts.py
```

## Pre-Prod hardening

### Cooldown и force для sync

- `GETCOURSE_SYNC_COOLDOWN_MINUTES=360` — минимальный интервал между sync.
- `GETCOURSE_SYNC_FORCE_ROLE=admin` — роль, которая может использовать `force=true`.
- Повторный sync до конца cooldown вернёт `429`:
  - `{"ok":false,"detail":"Sync cooldown active","nextAllowedAt":"...","cooldownMinutes":360}`
- Параллельный sync вернёт `409`:
  - `{"ok":false,"detail":"Sync already running"}`

Пример:

```bash
curl -i "http://localhost:8000/api/crm/integrations/getcourse/ping" -H "Authorization: Bearer <TOKEN>"
curl -i -X POST "http://localhost:8000/api/crm/integrations/getcourse/sync" -H "Authorization: Bearer <TOKEN>"
curl -i -X POST "http://localhost:8000/api/crm/integrations/getcourse/sync" -H "Authorization: Bearer <TOKEN>"
curl -i -X POST "http://localhost:8000/api/crm/integrations/getcourse/sync?force=true" -H "Authorization: Bearer <TOKEN>"
curl -i "http://localhost:8000/api/crm/catalog?limit=50&offset=0" -H "Authorization: Bearer <TOKEN>"
```

### Cron sync в Docker

- `GETCOURSE_CRON_ENABLED=true|false` (по умолчанию `false`)
- `GETCOURSE_CRON_INTERVAL_MINUTES=360`
- Сервис `getcourse_cron` доступен только в dev override (`docker-compose.dev.yml`).

Проверка:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f getcourse_cron
```

### Health endpoints

- `/healthz` — лёгкий health (без DB)
- `/readyz` — проверка доступности DB

Проверка:

```bash
curl -i http://localhost:8000/healthz
curl -i http://localhost:8000/readyz
```

### Миграции

Runtime `ALTER TABLE` убраны из `core/main.py`. Миграции запускаются отдельным сервисом `migrate`:

```bash
docker-compose up -d --build migrate
docker-compose logs migrate
```

Локальный запуск:

```bash
python scripts/run_migrations.py
```

Доступны отдельные idempotent-скрипты:
- `scripts/migrate_events_external.py`
- `scripts/migrate_payments_mvp.py`
- `scripts/migrate_funnel_contacts.py`
- `scripts/migrate_catalog_items.py`
- `scripts/migrate_integration_state.py`

### Secrets hygiene

- Не храните секреты в Git.
- Используйте только `.env`/секрет-хранилище.
- В логах маскируются `key=...` и `Bearer ...`.

### OpenAPI в production

При `ENVIRONMENT=production` отключаются:
- `/docs`
- `/redoc`
- `/openapi.json`

## OpenRouter (runtime smoke)

Env:

```bash
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=minimax/minimax-m2.5
export OPENROUTER_HTTP_REFERER=https://example.com
export OPENROUTER_X_TITLE="Renata Promotion"
export OPENROUTER_REASONING=false
```

Проверка backend ping (JWT required):

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/ai/ping
```

Smoke без UI:

```bash
python scripts/smoke_openrouter.py
```

Ожидаемый результат: `OK <длина_ответа>`.

## Локальный RAG (MVP)

Локальная база знаний читается из `rag_data/*.md` и `rag_data/*.txt`:
- `rag_data/getcourse.md`
- `rag_data/gestalt.md`
- `rag_data/faq.md`
- `rag_data/offers.md`

Эти файлы нужно заполнить вручную актуальным контентом проекта.

Env:
- `RAG_ENABLED=true`
- `RAG_TOP_K=5`
- `RAG_MIN_SCORE=0.08`
- `RAG_DATA_DIR=rag_data`

Smoke:

```bash
python scripts/rag_smoke.py
python scripts/rag_smoke.py "как записаться на консультацию"
```

Проверка private channel (admin JWT):

```bash
curl -X POST "http://localhost:8000/api/crm/subscriptions/private-channel/mark-paid?user_id=<TG_OR_INTERNAL_ID>" \
  -H "Authorization: Bearer <JWT>"

curl "http://localhost:8000/api/crm/subscriptions/private-channel/invite?user_id=<TG_OR_INTERNAL_ID>" \
  -H "Authorization: Bearer <JWT>"
```

## Production deployment

Рекомендуемый VPS для MVP:
- 2 vCPU
- 4 GB RAM
- 40-60 GB NVMe

База данных:
- можно оставить текущую managed DB (например Timeweb) на этом этапе;
- для цели «всё в одном месте» следующий шаг: перенести Postgres на тот же VPS или выбрать один провайдер и для приложения, и для DB.

Прод-компоновка:
- используйте `compose.prod.yml` (без `db` и без cron);
- у сервисов `restart: unless-stopped`;
- все переменные берутся из `.env`.

Шаги деплоя:

```bash
# 1) Docker + compose plugin
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER

# 2) Код
git clone <repo-url>
cd promotion_Renata/project_root

# 3) Конфигурация
cp .env.example .env
# заполните .env (DB, JWT, BOT_TOKEN, OPENROUTER_*)

# 4) Запуск
docker compose -f compose.prod.yml up -d --build

# 5) Проверка
curl -i http://localhost:8000/healthz
curl -i http://localhost:8000/readyz
```
