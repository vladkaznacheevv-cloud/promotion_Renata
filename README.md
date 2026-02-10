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

## GetCourse (MVP)

ENV:
- `GETCOURSE_ENABLED`
- `GETCOURSE_BASE_URL`
- `GETCOURSE_API_KEY`

Что делает синхронизация:
- читает сущности из GetCourse (products/courses/webinars/pages/deals, в зависимости от доступных API endpoints);
- импортирует в `events` сущности с датой/временем (`start_at`);
- импортирует в `catalog_items` сущности без даты (каталог курсов/продуктов);
- делает `upsert` по связке `external_source='getcourse' + external_id` (повторный sync не создаёт дубликаты);
- обновляет поля `title`, `description` (html -> текст), `link_getcourse`, `price`, `date`, `location`, `status` для событий;
- обновляет поля `title`, `description`, `price`, `currency`, `item_type`, `status`, `link_getcourse` для каталога.

Проверка summary:

```bash
curl -i http://localhost/api/crm/integrations/getcourse/summary -H "Authorization: Bearer <TOKEN>"
```

Синхронизация (admin):

```bash
curl -i -X POST http://localhost/api/crm/integrations/getcourse/sync -H "Authorization: Bearer <TOKEN>"
```

Пример ответа `sync`/`summary`:

```json
{
  "enabled": true,
  "status": "OK",
  "last_sync_at": "2026-02-10T12:00:00+00:00",
  "fetched": 8,
  "imported": {
    "created": 2,
    "updated": 3,
    "skipped": 1,
    "no_date": 2
  },
  "importedEvents": {
    "created": 2,
    "updated": 3,
    "skipped": 1,
    "no_date": 2
  },
  "importedCatalog": {
    "created": 1,
    "updated": 1,
    "skipped": 0
  },
  "counts": {
    "courses": 3,
    "products": 2,
    "events": 3,
    "catalog_items": 4,
    "fetched": 8,
    "created": 2,
    "updated": 3,
    "skipped": 1,
    "no_date": 2
  }
}
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
