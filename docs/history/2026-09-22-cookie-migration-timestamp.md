# 2026-09-22: cookie migration — уникальный timestamp

## Зачем

Два файла в `supabase/migrations/` имели один префикс `20260922120000`:

- `…_case_reactivation_touches.sql`
- `…_client_cookie_consent_once.sql` (из #17)

Кастомный runner на filename это переживает, но Supabase CLI / сортировка версий — нет.

## Что сделано

- Переименовано в `20260922130000_client_cookie_consent_once.sql`
- SQL без изменений смысла (`IF NOT EXISTS`)

## Проверено

- Локально: файл UTF-8, уникальный timestamp
- Применение на prod DB — отдельным шагом (SSH/PG)
