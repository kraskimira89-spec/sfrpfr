# 2026-10-21 — Staff docs выпуск 1 (текст / чат / дубли)

## Сделано

- Staff API: `content_preview` полный (до 2000) + `content_summary` отдельно; operator без OCR.
- Таблица: Оригинал / Скачать / Текст; «Краткое описание.» подписано; «Проверить текст» → оригинал + текст.
- Дубли: группировка exact `checksum_sha256` + раскрываемая история; разные байты не сливать.
- Чат: `doc_id=<uuid>` в журнале → staff signed-url; без id — не открывать по имени; дедуп журнала по id.

## Не в этом PR (выпуск 2)

- «Проверить документы» всё ещё `request_pipeline_run` (статус/audit), не persistable extract/classify/kit job.

## Проверено

- pytest: staff text, case_chat_log, admin_portal, signed_url, max_document_type
- node dedupe tests; `npx tsc --noEmit` в apps/admin; ruff
