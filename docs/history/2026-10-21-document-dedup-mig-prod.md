# 2026-10-21 — миграция document dedup на prod

## Контекст

PR #173 (код SHA-256 дедупа) на App-VPS, race-защита в PG слабее без
таблиц `case_document_checksums` + `document_upload_events`. Файл в репо:
`supabase/migrations/20261021200000_document_dedup_checksum_events.sql`.

## Факт по БД (supabase2, `194.67.116.168`)

- DDL: обе таблицы + 6 индексов (включая PK `(case_id, checksum_sha256)`
  и partial unique на `event_id` / `attachment_id`) — **созданы**.
- Backfill из `documents`: **3** строки в `case_document_checksums`
  (исторические дубли не удаляли).
- `document_upload_events`: 0 строк.
- RLS + `REVOKE` anon/authenticated + `GRANT` service_role — как у
  `staff_document_check_jobs` (в SQL-миграции grants не было; без них
  PostgREST не отдаёт таблицы service_role).
- Реестр `sfrfr_ops.schema_migrations`: запись добавлена ролью
  **`supabase_admin`**.
- `NOTIFY pgrst, 'reload schema'`.
- PostgREST: `GET .../rest/v1/case_document_checksums?limit=0` → **200** `[]`;
  `document_upload_events` → **200** `[]`.

## Как применено

1. SCP SQL → `/tmp/sfrfr-migrations/…` на DB-VM.
2. `psql -U postgres` в контейнере `db`: SQL миграции.
3. grants/RLS отдельно (см. выше).
4. `INSERT` в `sfrfr_ops.schema_migrations` от **`supabase_admin`**.
5. reload schema cache.

Канон: `scripts/vm_supabase_apply_migrations.sh` /
`docs/history/2026-10-21-staff-docs-mig-prod.md`.
`deploy-vps.yml` миграции не применяет.

SFRFR-81 не закрывали.
