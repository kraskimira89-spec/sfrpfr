# SFRFR-110: контрольная точка — точечная операция исправления даты

**База PR:** `origin/main` (`eea343e3…`, канон #262).
**Не** база #267 / стек #261–#266 — реализация не зависит от MAX-политик.
**Auto-merge OFF.** Merge / deploy / миграции / live MAX / E01-wire / закрытие SFRFR-110 — **не разрешены** этим отчётом.

## Контракт операции

```text
CorrectPeriodDateCommand
→ staff auth + case_accessible
→ validate shape/date/interval
→ store.apply_correction (одна транзакция / CAS)
→ CorrectPeriodDateResult + period_date_corrected (только после записи)
```

| Исход | Enum |
|---|---|
| Исправление сохранено | `saved` |
| Повтор той же операции | `idempotent_replay` |
| Конфликт версии | `version_conflict` |
| Недопустимые данные | `invalid_data` |
| Нет доступа / нет записи | `not_found_or_forbidden` |
| Отказ записи | `write_rejected` |
| Тот же op_id, другое тело | `op_id_payload_conflict` |
| Неизвестный исход | `unknown` → `reconcile_unknown` |

`файл::функция`:

- `services/period_date_correction.py::correct_period_date`
- `db/period_date_store.py::InMemoryPeriodDateStore` / `PostgresPeriodDateStore`
- `db/case_repository.py::save_pipeline_snapshot` (merge `staff_date_correction`)

Нет публичного HTTP / MAX-команды.

## Решение по схеме (без миграции)

| Требование | Как закрыто без миграции | Риск |
|---|---|---|
| Атомарность version+write | Postgres: `SELECT … FOR UPDATE` + `UPDATE … WHERE updated_at = expected` в одной TX; событие embedded в period JSON | — |
| Аудит before/after | `staff_date_correction` в том же UPDATE (не отдельный `access_audit`) | Журнал `access_audit` не дублирует событие |
| Стабильный period_id | Обязателен в команде; индекс массива не используется | Старые периоды без `period_id` → `not_found` до проставления id |
| Pipeline overwrite | `merge_periods_preserve_corrections` в `save_pipeline_snapshot` | Read+upsert через PostgREST **не** `FOR UPDATE` — гонка snapshot↔snapshot остаётся остаточным риском |
| Dependents | `needs_recheck`, снятие `recalculated` | Не полный реестр зависимостей |

**Стоп по миграции не активирован:** условный JSON-version без CAS не применялся.
Если владелец потребует отдельную таблицу `period_date_operations` / колонку `row_version` — см. предложение ниже (не применять без OK).

### Предложение миграции (только если остаточный риск неприемлем)

```sql
-- НЕ ПРИМЕНЯТЬ без отдельного разрешения
-- create table public.period_date_operations (
--   operation_id uuid primary key,
--   case_id uuid not null references public.cases(id),
--   payload jsonb not null,
--   event jsonb not null,
--   created_at timestamptz not null default now()
-- );
-- alter table public.case_pipeline_data
--   add column if not exists row_version bigint not null default 1;
```

Откат: `drop table period_date_operations; drop column row_version`.

## Изменённые write-пути

| Путь | Изменение |
|---|---|
| Новый: `PostgresPeriodDateStore.apply_correction` | Точечная правка даты |
| `CaseRepository.save_pipeline_snapshot` | Preserve staff corrections |
| MAX / portal HTTP | **не** затронуты |

## Тесты

```text
SHA: b7951375d5ceaff97e802c4d01b8167034445080
Unit:
  .\.venv\Scripts\python.exe -m pytest tests/unit/test_period_date_correction.py -q --basetemp=.tmp_pytest_date_op
  → 13 passed (локально на реализации)

Integration PG:
  .\.venv\Scripts\python.exe -m pytest tests/integration/test_period_date_correction_pg.py -q
  → SKIP: database_reachable=False (127.0.0.1:15433 не отвечает; Docker Desktop недоступен)
```

**Блокер доказательства атомарности на реальной БД:** инфраструктура тестовой БД.
Mock/InMemory — дополнение, не замена. Приёмку CAS на PG считать невыполненной до зелёного прогона integration.

## E/F-матрица (фрагмент)

| ID | Статус после этого PR |
|---|---|
| E01 операция записи | **реализована в коде** (staff/job store); **не** принята на PG; **E01-wire нет** |
| E01 клиентский ответ | GAP |
| E05/F04 prod adapter | без изменений |
| Close SFRFR-110 | **нет** |

## Остаточные риски

1. Integration PG не прогнан (БД недоступна).
2. `save_pipeline_snapshot` merge через Supabase read+upsert без row lock.
3. Периоды без `period_id` неисправимы этой операцией.
4. Нет HTTP/job wiring — только библиотека операции.
5. Стек #261–#266 не подключён (намеренно).

## Рекомендация

Не merge без: (a) зелёного CI, (b) по возможности зелёного PG integration на тестовой БД, (c) отдельного разрешения владельца.
E01-wire и закрытие SFRFR-110 — следующие этапы.
