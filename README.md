# promotion_Renata

## Запуск Docker-стека

### Production (основной контур)

```bash
docker compose -f compose.prod.yml up -d --build
docker compose -f compose.prod.yml ps
python scripts/compose_doctor.py
```

Runtime entrypoints:
- `migrate`: `python scripts/run_migrations.py`
- `web`: `uvicorn core.main:app --host 0.0.0.0 --port 8000`
- `bot`: `python -m telegram_bot.main`
- `frontend`: `nginx` (из `crm_web/admin-panel/Dockerfile`)

Порты в production compose (для подготовки HTTPS на хосте):
- `web`: `127.0.0.1:8000:8000`
- `frontend`: `127.0.0.1:8080:80`
- `bot`: без публичных портов

Проверка после `up`:

```bash
docker compose -f compose.prod.yml config | grep -n "ports\\|published"
docker ps --format "table {{.Names}}\t{{.Ports}}"
ss -lntp | egrep ":80|:443|:8000|:8080"
```

Ожидаемо:
- нет `0.0.0.0:80->...` у compose `frontend`
- `127.0.0.1:8000->8000/tcp` (web)
- `127.0.0.1:8080->80/tcp` (frontend)
- порт `80` свободен для nginx/certbot на хосте

### Development (локально)

Базовый `docker-compose.yml` рассчитан на внешнюю БД (`DATABASE_URL` / `DB_*`), без `db` и без `getcourse_cron`.

Локальная разработка со встроенным Postgres и cron:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

Сервисы:
- `frontend`: `http://localhost`
- `backend`: `http://localhost:8000/docs`
- `crm ping`: `http://localhost/api/crm/ping`

## YooKassa (game10) — receipt / чек

Если YooKassa возвращает `400 Receipt is missing or illegal` при создании платежа:
- убедитесь, что в запросе передаётся `receipt`
- в `receipt.customer` есть хотя бы `email` или `phone` пользователя
- `vat_code=1` (без НДС)
- для УСН используйте `YOOKASSA_TAX_SYSTEM_CODE=2` (по умолчанию)
- если у клиента в БД нет `email/phone`, бот в сценарии `Игра 10:0 -> Оплатить 5 000 ₽` сам запросит телефон или email для чека, сохранит контакт и повторит создание платежа
- если ссылка оплаты устарела и YooKassa показывает `Время истекло`, используйте кнопку `Обновить ссылку` — backend создаст новый платёж (или переиспользует только свежий `pending` в пределах `YOOKASSA_REUSE_TTL_MINUTES`, по умолчанию 15 минут)
- если у пользователя нет телефона/email для чека, бот сам запросит контакт (телефон или email), сохранит его и автоматически повторит создание платежа
- тестовая кнопка `Тестовая оплата 50 ₽` по умолчанию скрыта; она видна админу (`ADMIN_CHAT_ID`) и может быть включена для всех через `GAME10_TEST_PAYMENT_ENABLED=true`

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
docker-compose exec web python scripts/legacy/fix_mojibake.py
```

Применить изменения:

```bash
docker-compose exec web python scripts/legacy/fix_mojibake.py --apply
```

Ограничить проверку (диагностика):

```bash
docker-compose exec web python scripts/legacy/fix_mojibake.py --limit 50
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
docker-compose exec web python scripts/legacy/migrate_payments_mvp.py
docker-compose exec web python scripts/legacy/migrate_funnel_contacts.py
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

Idempotent-скрипты старых миграций перенесены в legacy-папку:
- `scripts/legacy/migrate_events_external.py`
- `scripts/legacy/migrate_payments_mvp.py`
- `scripts/legacy/migrate_funnel_contacts.py`
- `scripts/legacy/migrate_catalog_items.py`
- `scripts/legacy/migrate_integration_state.py`

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

## RAG диагностика (production)

RAG читает:
- `default` коллекцию из корня `rag_data/*.md|*.txt`
- дополнительные коллекции из подпапок `rag_data/<collection_name>/...`
- вложенные коллекции тоже поддерживаются (пример: `rag_data/programs/supervision/*.md` -> коллекция `programs/supervision`)

Примеры файлов:
- `rag_data/getcourse.md` (default)
- `rag_data/gestalt/overview.md` (collection `gestalt`)
- `rag_data/game10/overview.md` (collection `game10`)
- `rag_data/programs/<name>/intro.md` (collection `programs/<name>`)

Env (web/bot):
- `RAG_ENABLED=true`
- `RAG_TOP_K=6`
- `RAG_MIN_SCORE=0.08`
- `RAG_DATA_DIR=/app/rag_data` (в Docker) / `rag_data` (локально)
- `RAG_MAX_CONTEXT_CHARS=5000`

### (а) Проверка файлов на хосте

```bash
ls -la rag_data
find rag_data -maxdepth 3 -type f -name "*.md" -print
```

### (б) Проверка файлов внутри bot/web контейнеров

```bash
docker compose -f compose.prod.yml exec -T bot ls -la /app/rag_data
docker compose -f compose.prod.yml exec -T bot find /app/rag_data -maxdepth 3 -type f -name "*.md" -print
docker compose -f compose.prod.yml exec -T web ls -la /app/rag_data
```

### (в) `rag_doctor --list`

```bash
python scripts/rag_doctor.py --help
python scripts/rag_doctor.py --list
docker compose -f compose.prod.yml exec -T web python scripts/rag_doctor.py --list
```

### (г) `rag_doctor --query` (default / game10 / gestalt)

```bash
python scripts/rag_doctor.py --query "что такое игра 10:0" --collection game10
python scripts/rag_doctor.py --query "гештальт 1 ступень" --collection gestalt
python scripts/rag_doctor.py --query "игра 10:0" --collections all
python scripts/rag_doctor.py --query "игра 10:0" --collections game10,gestalt
docker compose -f compose.prod.yml exec -T web python scripts/rag_doctor.py --query "что такое игра 10:0" --collection game10
```

### (д) `/rag_debug` в боте

- Команда: `/rag_debug <query>`
- Если `ADMIN_CHAT_ID` задан, команда доступна только админу.
- Если `ADMIN_CHAT_ID` не задан, бот явно показывает предупреждение, что команда открыта.
- В выводе отображаются: обнаруженные коллекции, trace по query, trace последнего ответа (`rag_used_collection`, `rag_hits`, `fallback_to_default`, `fallback_to_model`).

## Ключевые скрипты и legacy

Оставлены в `scripts/` (активно используются):
- `scripts/run_migrations.py`
- `scripts/smoke_openrouter.py`
- `scripts/rag_smoke.py`
- `scripts/rag_doctor.py`
- `scripts/create_admin_user.py`
- `scripts/seed_crm.py`
- `scripts/db_ping.py`

Перенесены как legacy/one-off:
- `scripts/legacy/*` (старые миграции и encoding-фиксы)
- `legacy/tools/run_all.py`
- `legacy/tools/create_models.py`
- `legacy/tools/remove_bom.py`

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
python scripts/compose_doctor.py

# 5) Проверка
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
curl -i http://127.0.0.1:8080/
docker ps --format "table {{.Names}}\t{{.Ports}}"
ss -lntp | egrep ":80|:443|:8000|:8080"
```

## Домены и HTTPS (runbook, подготовка)

Текущий `compose.prod.yml` специально не занимает внешний `:80`:
- `frontend` слушает `127.0.0.1:8080`
- `web` слушает `127.0.0.1:8000`

Это позволяет поднять reverse proxy на хосте (nginx + certbot) для доменов без изменения внутренних API-контрактов.

Шаблоны в репозитории:
- `deploy/nginx/renatapromotion.conf` — host nginx для `crm.<domain>` и `api.<domain>`
- `deploy/nginx/limits.conf` — `limit_req_zone` (кладётся в `/etc/nginx/conf.d/`, не в `server {}`)
- `scripts/nginx_doctor.py` — безопасная диагностика (checks + copy-paste команды, без `systemctl`)

Шаги:

1. DNS:
- создайте `A`-записи `crm.<DOMAIN>` -> `<SERVER_IP>`
- создайте `A`-записи `api.<DOMAIN>` -> `<SERVER_IP>`

2. Проверьте, какие порты должны быть заняты/свободны:
- `80` / `443` — должен занимать хостовый nginx (после его установки)
- `127.0.0.1:8000` — контейнер `web`
- `127.0.0.1:8080` — контейнер `frontend`

До установки хостового nginx внешний `:80` и `:443` должны быть свободны.

Проверка:

```bash
ss -lntp | egrep ":80|:443|:8000|:8080"
docker ps --format "table {{.Names}}\t{{.Ports}}"
python scripts/nginx_doctor.py
```

3. Поднимите reverse proxy на хосте (рекомендуемый вариант):
- `nginx` на хосте
- `certbot` (HTTP-01) на `:80`
- прокси:
  - `crm.<DOMAIN>` -> `http://127.0.0.1:8080`
  - `api.<DOMAIN>` -> `http://127.0.0.1:8000`
- используйте шаблон `deploy/nginx/renatapromotion.conf` как стартовую точку
- `limit_req_zone` вынесите в `deploy/nginx/limits.conf` (http-context)

4. Обновите `.env` (не коммитьте):
- `PUBLIC_BASE_URL=https://api.<DOMAIN>`
- `YOOKASSA_WEBHOOK_TOKEN=<secret>`
- `BOT_API_TOKEN=<internal bot->web token>`
- `YOOKASSA_SHOP_ID=<shop/account id>`
- `YOOKASSA_SECRET_KEY=<secret>`
- `YOOKASSA_TAX_SYSTEM_CODE=2` (УСН доходы, по умолчанию)
- `YOOKASSA_VAT_CODE=1` (без НДС, по умолчанию)
- укажите webhook YooKassa на `https://api.<DOMAIN>/api/webhooks/yookassa/<YOOKASSA_WEBHOOK_TOKEN>`

Примечания:
- фронт уже собран с `VITE_API_BASE_URL=/api`, поэтому CRM продолжит работать через `crm.<DOMAIN>/api/*` при проксировании на backend;
- HTTPS в compose сейчас не включается намеренно (TLS завершается на хостовом reverse proxy).

## PROD CHECKLIST (today)

1. Docker compose сервисы и health:

```bash
docker compose -f compose.prod.yml up -d --build
docker compose -f compose.prod.yml ps
docker ps --format "table {{.Names}}\t{{.Ports}}"
ss -lntp | egrep ":80|:443|:8000|:8080"
```

Ожидаемо:
- `web` -> `127.0.0.1:8000`
- `frontend` -> `127.0.0.1:8080`
- `80/443` свободны для host nginx (до его запуска)

2. Host nginx routing check:

```bash
sudo cp deploy/nginx/renatapromotion.conf /etc/nginx/sites-available/renatapromotion.conf
sudo cp deploy/nginx/limits.conf /etc/nginx/conf.d/limits.conf
sudo ln -sfn /etc/nginx/sites-available/renatapromotion.conf /etc/nginx/sites-enabled/renatapromotion.conf
sudo nginx -t && sudo systemctl reload nginx
sh scripts/nginx_header_check.sh
python scripts/nginx_doctor.py
```

3. HTTPS / certbot (пример):

```bash
sudo certbot --nginx -d crm.renatapromotion.ru -d api.renatapromotion.ru
```

4. YooKassa env checklist (`.env`, не коммитить):
- `PUBLIC_BASE_URL=https://api.renatapromotion.ru`
- `YOOKASSA_WEBHOOK_TOKEN=<secret>`
- `BOT_API_TOKEN=<internal token bot->web>`
- `YOOKASSA_SHOP_ID=<shop/account id>`
- `YOOKASSA_SECRET_KEY=<secret>`
- `YOOKASSA_TAX_SYSTEM_CODE=2`
- `YOOKASSA_VAT_CODE=1`
- `TELEGRAM_PRIVATE_CHANNEL_ID=-100...` (канал, где бот админ)

Проверка env + create-payment smoke:

```bash
python scripts/yookassa_smoke.py
python scripts/yookassa_smoke.py --tg-id <TG_ID>
```

5. Smoke тест оплаты (цепочка):
- create payment (`/api/payments/game10/create`) -> получен `payment_id` + `confirmation_url`
- webhook endpoint:
  - `GET /api/webhooks/yookassa/<token>` -> `405` (это нормально, endpoint только POST)
  - `POST /api/webhooks/yookassa/<token>` -> обновляет статус и отправляет TG кнопку вступления
- join request flow:
  - оплаченный пользователь -> approve
  - неоплаченный пользователь -> decline + предложение оплатить

Примеры:

```bash
curl -i -H "Host: api.renatapromotion.ru" http://127.0.0.1/healthz
curl -i -H "Host: api.renatapromotion.ru" http://127.0.0.1/api/healthz
curl -i -X GET "https://api.renatapromotion.ru/api/webhooks/yookassa/<TOKEN>"
```

6. Troubleshooting:
- `nginx returns default page` -> проверьте `sites-enabled` symlink и `server_name`
- `/api/* gives 404 html` -> неправильный `location /api/` / `proxy_pass` в host nginx
- `YooKassa Receipt is missing` -> проверьте `receipt`, `receipt.customer`, `vat_code=1`
- бот не approve join request -> проверьте `TELEGRAM_PRIVATE_CHANNEL_ID`, права бота в канале (admin), и paid-flag в БД (`/pay_debug`, `/rag_debug` тут не поможет)

### Почему `curl /api/healthz` может быть `404` и как правильно тестировать

Базовые health endpoints FastAPI существуют на:
- `/healthz`
- `/readyz`

На `api.<DOMAIN>` можно тестировать напрямую:

```bash
curl -i -H "Host: api.<DOMAIN>" http://127.0.0.1/healthz
curl -i -H "Host: api.<DOMAIN>" http://127.0.0.1/readyz
```

Пути `/api/healthz` и `/api/readyz` работают только если в host nginx добавлены алиасы
(`/api/healthz -> /healthz`, `/api/readyz -> /readyz`). Шаблон `deploy/nginx/renatapromotion.conf`
их уже содержит.

Дополнительно (через CRM vhost):

```bash
curl -i -H "Host: crm.<DOMAIN>" http://127.0.0.1/api/healthz
curl -i -H "Host: crm.<DOMAIN>" http://127.0.0.1/api/readyz
```
