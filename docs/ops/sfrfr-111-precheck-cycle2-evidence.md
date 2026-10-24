# SFRFR-111 цикл 2: job recovery + precheck:* + периоды

**Head #269:** см. `git rev-parse` после push (ветка `feat/sfrfr-primary-doc-precheck`).  
**PR:** https://github.com/kraskimira89-spec/sfrpfr/pull/269  
**Unit:** 44 passed (`test_primary_doc_precheck` + lifecycle/callbacks + staff_document_check).  
**Не** merge / deploy / live MAX / закрытие SFRFR-110/111.

## Формулировка статуса

> Реализован расширенный срез предпроверки: recovery job (unit),  
> эфемерное извлечение периодов без записи в pipeline, callback `precheck:*`,  
> ужесточённый офер, регистрация ask_staff. Полный browser smoke и PG/worker  
> integration ещё **не** закрывают DoD.

## Команды

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_primary_doc_precheck.py `
  tests/unit/test_precheck_job_lifecycle_and_callbacks.py `
  tests/unit/test_staff_document_check.py -q --basetemp=tmp/pytest-precheck-c2
```

Результат: **44 passed**.

## Job lifecycle (доказано unit)

| Требование | Механизм | Доказательство |
|---|---|---|
| Запись до обработки | `enqueue` → insert `queued` до BackgroundTasks | staff_document_check unit |
| Подхват незавершённых | `reclaim_stale_running_jobs` + `process_next` в ingest-worker | `test_reclaim_stale_running_requeues` |
| Нет второго результата/notify | early return finalized; `_maybe_retry_client_notify` один догон | unit + retry test |
| Результат есть, enqueue нет | догон notify без пересчёта | `test_finalized_job_retries_missing_notify_once` |
| Зависшие | stale running → requeue или failed | reclaim + exhausted |
| Ошибка | status=failed + last_error | lifecycle |
| Не HTTP sync | обработка только BackgroundTasks / worker poll | код маршрута |

**Ограничение:** reclaim доказан mock-ом Supabase, не живым PG restart процесса.

## Пустой pipeline

`periods_for_precheck`: читает pipeline; иначе эфемерный `extract_periods` **без** upsert в `case_pipeline_data`.  
Состояния: `documents_missing` / `extract_not_run` / `extract_failed` / `extract_empty_unreadable` / `periods_ready`.  
Пустые периоды **не** дают `no_discrepancies_found`.

## Callback `precheck:*`

| Subcode | Вход | Права | Действие | Повтор | Ответ |
|---|---|---|---|---|---|
| `summary` / `status` | payload + case | привязка max→case | актуальное резюме | идемпотентно | текст + кнопки версии |
| `explain` | + check_id? | то же | по сохранённой находке + limitations | идемпотентно | без «недоплаты» |
| `need_docs` / `upload` | | | маршрут досылки | идемпотентно | инструкция загрузки |
| `offer_info` | | | состав/цена из recommendation | без заказа | блок если офер закрыт |
| `order` | | | handoff на существующий маршрут | **не** создаёт заказ | `precheck_order_handoff` |
| `decline` | | | `precheck_offer_declined` | повтор безопасен | офер снят |
| `ask_staff` | + max_user | | флаг запроса, `confirmed=false` | не объявляет «подключён» | registered |
| stale check_id | | | show current | | `stale_show_current` |

## Примеры outcome (unit)

| Сценарий | outcome | offer |
|---|---|---|
| Различие дат ИЛС↔труд | `discrepancies_found` + findings | по правилам офера |
| Совпадение периодов | `no_discrepancies_found` | false |
| Нет документов | `insufficient_documents` | false |

## Офер (доп. фильтры)

Блоки: paid/pending заказ, decline, catalog None / order status unknown, low-confidence OCR-only, insufficient/tech.  
Unknown статус оплаты ≠ «не оплачено».

## Этапы SFRFR-112…117

| Ключ | Статус Tracker | Прогресс цикла 2 |
|---|---|---|
| SFRFR-112 | Открыт | контракт/evidence docs |
| SFRFR-113 | Открыт | reclaim + enqueue; PG restart не доказан |
| SFRFR-114 | Открыт | сопоставление + ephemeral periods |
| SFRFR-115 | Открыт | резюме/recommendation/offer gates |
| SFRFR-116 | Открыт | `precheck:*` wired; live MAX нет |
| SFRFR-117 | Открыт | unit 44; browser/PG/E2E нет |

## Не доказано этим циклом

- Browser smoke карточки дела
- Реальный PG concurrent job / process restart
- Полный E2E MAX live
- Wiring `precheck:order` → pay-link API
- Чужой user access (нужен integration с привязкой max_user)
