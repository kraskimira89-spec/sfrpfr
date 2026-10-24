# SFRFR-111 цикл 2: job recovery + precheck:* + периоды

**Head ветки:** см. PR #269 после push.  
**Не** merge / deploy / live MAX / закрытие SFRFR-110/111.

## Формулировка статуса

> Реализован расширенный срез предпроверки по отчёту исполнителя: recovery job,  
> эфемерное извлечение периодов без записи в pipeline, callback `precheck:*`,  
> ужесточённый офер. Полный browser smoke и PG/worker integration ещё **не**  
> закрывают DoD.

## Команды

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_primary_doc_precheck.py `
  tests/unit/test_precheck_job_lifecycle_and_callbacks.py `
  tests/unit/test_staff_document_check.py -q --basetemp=tmp/pytest-precheck-c2
```

## Job lifecycle (доказано unit)

| Требование | Механизм |
|---|---|
| Запись до обработки | `enqueue` → insert `queued` до BackgroundTasks |
| Подхват незавершённых | `reclaim_stale_running_jobs` + `process_next` в ingest-worker |
| Нет второго результата/notify | early return `result_already_finalized` / `notify_already_recorded` |
| Зависшие | stale running → requeue или failed |
| Ошибка | status=failed + last_error |
| Не HTTP sync | обработка только BackgroundTasks / worker poll |

## Пустой pipeline

`periods_for_precheck`: читает pipeline; иначе эфемерный `extract_periods` **без** upsert в `case_pipeline_data`.  
Состояния: `documents_missing` / `extract_not_run` / `extract_failed` / `extract_empty_unreadable` / `periods_ready`.  
Пустые периоды **не** дают `no_discrepancies_found`.

## Callback `precheck:*`

| Subcode | Поведение |
|---|---|
| summary / status | актуальное резюме |
| explain | по сохранённой находке + ограничения |
| need_docs / upload | маршрут досылки |
| offer_info | состав/цена из recommendation, без заказа |
| order | handoff; **не** создаёт заказ |
| decline | флаг отказа |
| ask_staff | текст без ложного «подключён» |

Stale check_id → show current. Чужой case — нет привязки max_user→case.

## Офер

Блоки: paid/pending заказ, decline, catalog None / order status unknown, low-confidence OCR-only, insufficient/tech.

## Не доказано этим циклом

- Browser smoke карточки дела
- Реальный PG concurrent job
- Полный E2E MAX live
- Wiring заказа на существующий pay-link из `precheck:order`
