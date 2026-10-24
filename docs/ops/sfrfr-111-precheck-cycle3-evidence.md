# SFRFR-111 цикл 3: замыкание handler + пустой pipeline

**Head #269:** `f3cfc270`  
**PR:** https://github.com/kraskimira89-spec/sfrpfr/pull/269  
**Не** merge / deploy / live MAX / prod-миграции / закрытие SFRFR-110/111. Auto-merge OFF.

## Формулировка

> Precheck v2 по отчёту на `86afa6e1` (21 passed). Далее на ветке #269: фактическая маршрутизация `precheck:*` через `handle_max_update` и эфемерное извлечение периодов при пустом pipeline. Инфраструктурная приёмка (тестовая БД / process restart / browser smoke) **открыта**.

## Команды

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_precheck_handler_routing.py `
  tests/unit/test_precheck_job_lifecycle_and_callbacks.py `
  tests/unit/test_primary_doc_precheck.py `
  tests/unit/test_staff_document_check.py -q --basetemp=tmp/pytest-precheck-c3
```

Результат цикла 3: **54 passed**.

## A. MAX-handler → precheck:*

| Проверка | Доказательство |
|---|---|
| Маршрут через реальный `handle_max_update` | `test_handler_routes_precheck_summary_to_reply` |
| Нет привязки дела | `precheck_no_case` |
| Stale check_id в payload | `stale_show_current` |
| `precheck:order` не создаёт заказ | `precheck_order_handoff` |
| Повтор summary идемпотентен | `test_handler_repeat_callback_idempotent_summary` |
| Кнопки с check_id | `precheck:<sub>:<check_id>` в `build_precheck_max_message` |

Код: `_handle_precheck_callback_event` в `handler.py`.

## B. Пустой pipeline

| Состояние | Поведение |
|---|---|
| documents_missing | не «нет расхождений» |
| extract_not_run / extract_failed / extract_empty_unreadable | kit_missing + ограничения |
| extract_partial | одна сторона; не полный комплект |
| periods_ready | обе стороны; provenance `pipeline` или `ephemeral_extract`/`ocr_artifact` |

Эфемерный extract **не** пишет в `case_pipeline_data`.

## Офер / заказ

- pending / unfinished order → block  
- ошибка чтения заказов → `status_unknown`, catalog amount сброшен → `catalog_unavailable`  
- decline / already ordered → block  

## Probe БД

> Probe (исторический) завершился без диагностического результата; схема не получена, причина завершения не установлена.

Новый безопасный скрипт (один запуск, без секретов в логе):

```powershell
.\.venv\Scripts\python.exe tools\precheck_db_probe.py --timeout-connect 5 --timeout-query 8
```

Без `PRECHECK_PROBE_DATABASE_URL` / `DATABASE_URL` → `RESULT: no_dsn` (exit 2). Production не используется.

## Инфраструктура (открыто)

- [ ] тестовая БД: save/reload result  
- [ ] process restart → reclaim  
- [ ] нет повторного notify (unit есть; PG — нет)  
- [ ] browser smoke  

## #41 / #42

Исключены из зависимостей SFRFR-111: на main уже есть кнопка и `DocumentCheckPanel`; PR — docs/HITL-воронка.
