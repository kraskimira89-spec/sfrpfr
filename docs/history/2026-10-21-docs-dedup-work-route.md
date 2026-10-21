# 2026-10-21 — Exact-dupe + «Работа с делом» (этапы 1–3/7 ТЗ)

## Сделано

1. **Дедуп до OCR** (`document_deduplication` + `create_quarantine_document`):
   - replay event_id/attachment_id → no-op;
   - SHA-256 + size = exact dupe (имя/время не ключ);
   - нет второй permanent-копии и ingest job;
   - restore при утрате оригинала;
   - реестр `case_document_checksums` + `document_upload_events` (миграция).
2. **UI**: одна таблица; ingest panel в свёрнутом техжурнале; дубли «Проверить документы» убраны из воронки.
3. **Маршрут** `work_route` (server SoT): проверка → сверка → проект; одна primary-кнопка.
4. **#172** staff docs-check сохранён; клиенту не шлём «разбор готов».

## Тесты

- `test_document_deduplication.py` (1–4, 6–8 + name)
- `test_document_deduplication_concurrency.py` (5)
- `test_case_work_route.py`

## Не в этом PR

- Полная сверка сведений со schema цитат (этап 4)
- HITL правки специалиста (этап 5)
- Закрытие SFRFR-81
