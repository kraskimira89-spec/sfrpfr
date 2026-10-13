# 2026-10-13 — догонка миграций на supabase2

## Контекст

После cutover на `194.67.116.168` (`/opt/sfrfr-supabase`) в дампе не хватало
схемы из репо: `document_ingest_jobs` → PGRST205 у `sfrfr-document-ingest`,
также `document_groups`, `case_messages.read_at_client` / `external_message_id`.

## Бэкап

`/srv/supabase-data/restore/pre-migrations-20261013T113051Z.dump`

## Применено (20 файлов + GRANT)

Реестр: `sfrfr_ops.schema_migrations` = **50/50** файлов из `supabase/migrations/`.

Ключевые: `max_intake`, `document_groups`, `document_ingest_jobs` (+ lock),
unified case chat / presence / outbox / bot_jobs / dedupe, payment nudges,
payments one-active, reactivation touches, OCR phase2, marketing_consents,
customer_journey (политики с `private.can_access_case` — хелперы уже в `private`).

`orders_finance_ops`: применены только DDL/индексы; **UPDATE backfill**
(`invoice_number` / `invoice_status` / `due_at`) **не выполнялись**.

Дополнительно на БД: `GRANT … TO service_role` на `document_ingest_jobs` /
`document_groups` (иначе PostgREST schema cache → PGRST205 после REVVOKE).
Канон в репо: `20261013120000_document_ingest_jobs_service_role.sql`.

## Проверки

- REST `document_ingest_jobs` → HTTP 200 `[]`
- `document_ingest_jobs_available` → True; worker `active`, queue empty
- `https://api.proverkastaza.ru/health` → ok
- Emergency leads `source=max`: 2 → дела созданы без дублей, pending flushed

## SFRFR-73

Инцидент (db-01 недоступна) закрыт cutover + догонкой схемы.
