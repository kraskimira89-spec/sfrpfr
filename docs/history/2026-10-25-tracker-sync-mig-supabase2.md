# 2026-10-25 — миграции tracker_sync на supabase2

## Цель

Накатить DDL outbox/inbox синхронизации Трекера на рабочую БД supabase2
(`194.67.116.168` / `https://supabase2.proverkastaza.ru`).

## Файлы

- `supabase/migrations/20261025120000_tracker_sync_outbox.sql`
- `supabase/migrations/20261025130000_tracker_sync_schema.sql`

## Применение

1. SCP → `/tmp/sfrfr-migrations-tracker/` на DB-VM `sfrfr-supabase-db-regru`.
2. `docker compose exec -T db psql -U supabase_admin -d postgres` + `ON_ERROR_STOP=1`.
3. `INSERT` в `sfrfr_ops.schema_migrations`.
4. `NOTIFY pgrst, 'reload schema'`.

## Проверка

| Объект | Результат |
|--------|-----------|
| `public.tracker_sync_outbox` | есть |
| schema `tracker_sync` | есть |
| таблицы | bindings, task_state, inbox, change_history, outbox, delivery_attempts |
| реестр | обе записи @ 2026-10-25 07:58 UTC |

## Не включалось

- `TRACKER_CASE_SYNC_ENABLED` на app
- webhook-автодействие в Трекере
- секреты webhook в `.env`

Код: PR [#282](https://github.com/kraskimira89-spec/sfrpfr/pull/282) (merged; #281 закрыт без merge) · задача [SFRFR-118](https://tracker.yandex.ru/SFRFR-118).  
Пакет выпуска / блокеры пилота: `docs/TRACKER/release-package-case-sync-pilot.md`.
