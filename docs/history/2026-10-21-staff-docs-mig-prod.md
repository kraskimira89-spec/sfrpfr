# 2026-10-21 — миграция staff_document_check_jobs на prod

## Контекст

PR #172 (код «Проверить документы») на App-VPS, но кнопка не принималась
без таблицы `staff_document_check_jobs`. Файл в репо:
`supabase/migrations/20261021120000_staff_document_check_jobs.sql`.

## Факт по БД (supabase2, `194.67.116.168`)

- DDL таблицы, 3 индекса + pkey, RLS, GRANT `service_role` — **уже были**
  (идемпотентный повтор дал только NOTICE `already exists`).
- В `sfrfr_ops.schema_migrations` записи **не было** (52 → после INSERT **53**).
- PostgREST: `GET .../rest/v1/staff_document_check_jobs?limit=0` → HTTP 200 `[]`.
- Строк в таблице: 0 (данных не трогали).

## Как применено / зарегистрировано

1. SCP SQL на DB-VM → `/tmp/sfrfr-migrations/…`.
2. `psql -U postgres` в контейнере `db`: повтор SQL (IF NOT EXISTS) — OK.
3. Реестр: `INSERT` в `sfrfr_ops.schema_migrations` от роли **`supabase_admin`**
   (роль `postgres` на этом стеке **не** superuser и без прав на `sfrfr_ops.*`).

Канон runner: `scripts/vm_supabase_apply_migrations.sh` (`COMPOSE_DIR=/opt/sfrfr-supabase/supabase/docker`,
`MIG_DIR=/tmp/sfrfr-migrations`). На текущем стеке для записи в реестр нужен
`supabase_admin`, иначе `permission denied for table schema_migrations`.

## Deploy path (важно)

`deploy-vps.yml` / `vps_deploy.sh` **не** применяют `supabase/migrations/`.
Миграции на prod БД — отдельный шаг на DB-VM (или точечный SQL + реестр),
см. `docs/ops/deploy-and-migrations.md`.

SFRFR-81 не закрывали.
