# 2026-10-21 — Staff docs выпуск 2 (реальная проверка)

## Сделано

- Кнопка «Проверить документы» → `POST .../request-review` ставит persistable job
  `staff_document_check_jobs` (fingerprint набора, дедуп active).
- Worker `document_ingest` обрабатывает staff-check раньше обычного ingest.
- После enqueue — фоновый process того же job_id (без второго enqueue).
- Объём: originals → embedded text PDF/DOCX → types → exact dupes → kit → result.
- OCR сканов только при `STAFF_DOCS_CHECK_ALLOW_OCR=true` (default false).
- Клиенту не шлём «разбор готов»; UI показывает staff-only карточку результата.
- Старые findings/analysis_notes помечены как «пайплайн», не как новая проверка.
- Stale при смене набора документов.
- «Сформировать проект» → отдельный `POST .../request-pipeline` (без docs-check).

## Миграция

`supabase/migrations/20261021120000_staff_document_check_jobs.sql` — нужна на prod
до приёмки кнопки.

## Не в этом PR

- Юр.анализ LLM / полный OCR-сервис
- Смена хранения / платежей / модели
- Закрытие SFRFR-81
