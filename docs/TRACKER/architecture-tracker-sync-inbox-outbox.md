# Архитектура inbox/outbox синхронизации с Яндекс Трекером

**Дата:** 2026-10-25  
**Задача:** [SFRFR-118](https://tracker.yandex.ru/SFRFR-118)  
**Статус:** схема в репо · очередь **CASE** создана · код в `main`/`prod` (`eb17ecb6`, PR #282) · DDL на **supabase2** · sync **выкл.** · wiring/worker/UI — см. [release-package-case-sync-pilot.md](release-package-case-sync-pilot.md)  
**Срез 1–2 (код):** [spec-tracker-sync-outbox.md](spec-tracker-sync-outbox.md) · PR #282 (заменил закрытый #281)  
**Диспетчерская карточка:** [spec-case-dispatch-card.md](spec-case-dispatch-card.md)

## 0. Принцип

> БД фиксирует подтверждённые факты. Трекер получает рабочую проекцию. Обратные webhook — команды, которые приложение проверяет. Ни webhook, ни ручной статус Трекера не подтверждают оплату, доставку или подачу.

Доставка — at-least-once; применение — локально идемпотентное; внешние исходы — через сверку (`uncertain`), не exactly-once.

## 1. Три независимых состояния

| Состояние | Владелец | Пример |
|---|---|---|
| Этап дела (13 ступеней) | приложение | `appeals_documents` |
| Рабочий статус задачи специалиста | Трекер (+ проверяемый sync) | `inProgress` |
| Состояние интеграции | сервис sync | `retry` / `uncertain` |

Ошибка sync ≠ «ошибочное дело» и ≠ откат оплаты.

### Владение полями

| Направление | Поля |
|---|---|
| App → Tracker | этап, `app_revision`, подтверждённые оплаты по услугам, готовность документов, результаты |
| Tracker → App | допустимые назначения, рабочие сроки, запросы действий, результаты работы сотрудника |
| Двусторонние | только с правилом конфликта + версией |
| Запрещено из Трекера | оплата, доставка, подача, юридический итог |

## 2. Аудит существующего контура (факт)

### `public.case_tracker_issues` (STAZH quality)

| Факт | Следствие |
|---|---|
| Связь `case_id` + `case_ref` + `tracker_issue_key` | Оставить для quality; не смешивать с `case_root` без `binding_kind` |
| Unique open: `(case_ref, issue_type)` where open | Дедуп quality, не покрывает work_item с разными `purpose_key` |
| `quality_issues.create_quality_issue_from_case` | Сначала `create_issue` API, потом INSERT в БД |
| Дубль — отдельный SELECT | Гонка двух запросов → два внешних issue возможны |
| Нет `tracker_issue_id` (numeric/cloud id) | Для webhook нужны оба: key и id |

**Для нового контура:** не копировать порядок «API create → потом БД». Нужны: резервирование binding / `purpose_key` до внешнего create, сверка при `outcome_unknown`, поиск дубля по `purpose_key`.

### Срез 1: `public.tracker_sync_outbox` (PR #281)

Упрощённый outbox проекции (без lease, без inbox). Целевая схема — `tracker_sync.*` ниже.  
Переход: после приёмки schema — перенести операции в `tracker_sync.outbox`, таблицу `public.tracker_sync_outbox` пометить deprecated / мигрировать строки.

### Клиент

- Sync STAZH: `__init__.py` (`create_issue`, retries).  
- Async транспорт: `client.py` (без write-retry; unknown → worker reconcile).

## 3. Целевая схема потока

```text
Яндекс Трекер
    │ HTTP webhook
    ▼
Webhook API  →  tracker_sync.inbox  →  Inbox worker
                                         │ GET issue
                                         ▼
                              bindings + task_state + history
                                         │
                                         ▼
                              tracker_sync.outbox → Outbox worker
                                         │
                              Tracker API / (позже MAX через app outbox)
```

Внешний HTTP **не** держит SQL-транзакцию.  
Webhook: быстрый 200 после commit inbox; повторы Трекера (timeout/500, до 5) — безопасны за счёт `dedupe_key`.

## 4. Связь с `case_tracker_issues`

| Реестр | Назначение |
|---|---|
| `case_tracker_issues` | Quality/SLA из admin (STAZH), issue_type ∈ fixed set |
| `tracker_sync.bindings` | `case_root` + `work_item` диспетчерской (очередь CASE/DELO после решения владельца) |

Не два реестра одной связи: quality остаётся в `case_tracker_issues`; диспетчерская — в `bindings`.  
Опционально позже: view/join по `tracker_issue_key` для UI.

`purpose_key` примеры:

```text
root
prepare_analysis:<order-id>
prepare_appeals:<order-id>
call:<submission-id>:checkpoint-10
review_response:<document-version-id>
```

## 5. Таблицы `tracker_sync` (черновик DDL)

Канон SQL: `supabase/migrations/20261025130000_tracker_sync_schema.sql`  
Схема: `bindings`, `task_state`, `inbox`, `change_history`, `outbox`, `delivery_attempts`.

Счётчики **не** сравнивать между собой: `app_revision` ≠ `tracker_version` ≠ `local_revision`.

### Dedupe webhook

| Вариант | Ключ |
|---|---|
| A: есть source_event_id | `org + source + source_event_id` |
| B: есть version | `org + issue_id + version + event_kind` |
| C: нет ни того ни другого | только сигнал «перечитать»; без необратимых команд |

Тот же `dedupe_key` + другой `payload_hash` → конфликт, не execute.

### Outbox states

`pending | processing | retry | uncertain | reconciling | succeeded | superseded | dead`  
`uncertain` → только сверка, не слепой повтор PATCH/transition/create.

## 6. План внедрения (согласованный порядок)

1. ~~Аудит DDL + клиент~~ (этот документ + §2).  
2. Mapping полей/владельцев — после выбора очереди CASE/DELO.  
3. Миграция schema (черновик в репо; apply — отдельное согласование).  
4. Входящий sync **только** рабочего статуса (inbox → task_state).  
5. Исходящая проекция этапов (evolve #281 → `tracker_sync.outbox`).  
6. Безопасные команды сотрудника (webhook envelope).  
7. Reconciliation + мониторинг.  
8. Напоминания / клиентские уведомления.

## 7. Приёмка (минимум)

- 20 повторов webhook → одно применение.  
- Тот же ключ, другой payload → reject/conflict.  
- Версия 12 после 13 не откатывает.  
- Два worker / потерянный lease → один commit.  
- Таймаут write → `uncertain` + сверка.  
- Ошибка Трекера не теряет оплату.  
- Нет цикла app↔Tracker.  
- История без лишних ПДн.

## 8. Срез 2 (после «да» владельца, 2026-10-25)

| Сделано | Не сделано |
|---|---|
| Очередь `CASE` в org | Локальные поля очереди в UI |
| `inbox.py` + unit (dedupe, version, forbid payment) | Postgres repository вместо in-memory |
| `POST /api/integrations/tracker/commands` (503 пока sync выкл.) | Автодействия Трекера на prod |
| DDL `tracker_sync.*` в репо | Apply на YC (`vm_supabase_apply_migrations.sh` после merge) |

Включение: `TRACKER_CASE_SYNC_ENABLED=1`, `TRACKER_WEBHOOK_SECRET`, `TRACKER_CASE_QUEUE=CASE`, apply миграций 20261025120000 + 20261025130000.

## 9. Долг

- Изменение порядка create в `quality_issues.py` / work_item: reserving binding до API create.  
- Перенос `public.tracker_sync_outbox` → `tracker_sync.outbox`.
