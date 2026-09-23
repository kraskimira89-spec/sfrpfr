# 2026-09-23 — Оригиналы загрузок сразу на Яндекс.Диск

## Проблема

На prod `DOCUMENT_INGEST_ASYNC=true`, но нет `ingest_status` / `document_ingest_jobs`.
Зеркало вызывалось только после ingest-job → **оригиналы PDF не попадали на Диск**.
В папках дел оставались тестовые `.txt` (ils/labor).

## Исправление

- `create_quarantine_document`: если jobs недоступны — сразу `mirror` байт оригинала в `incoming/`
- `store_document`: всегда зеркалит оригинал
- CLI `yandex-disk-backfill-uploads` — дозаливка из `storage/uploads`

Папка дела = UUID (без ФИО в пути).
