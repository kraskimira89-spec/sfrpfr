# SFRFR-110: атомарная граница date-op + snapshot (стоп / согласование)

Дата: 2026-10-24. PR: #268. **Не** разрешение на merge / миграции / deploy.

## Вывод по стоп-условию

Существующий PostgREST-путь `get_pipeline_row` + `upsert` + отдельный `audit()`
**не** даёт одной транзакции. В #268:

| Слой | Статус |
|---|---|
| Date-op (psycopg `FOR UPDATE` + CAS `updated_at` + embedded `period_date_corrected`) | Реализован в коде |
| Snapshot (psycopg `FOR UPDATE` + merge corrections + CAS; отсутствие ключа ≠ `[]`) | Реализован в коде (#268 follow-up) |
| Общий lock date-op ↔ snapshot в InMemory | Покрыт тестами A–E |
| PG integration (два соединения, барьеры) | Код тестов + `tools/date_op_pg` + CI `date-op-pg.yml`; **локально на агенте Docker отсутствует** — evidence ждём от CI |
| Writers вне store / прямой PostgREST | findings-upsert в admin переведён на snapshot CAS; **остальной service_role PostgREST** — блокер до RPC/revoke |
| Ledger `operation_id` | `staff_date_corrections[]` + latest marker; колонка/RPC — только по отдельному OK |
| `require_case` remap | Для write: `require_case_exact` (без подмены id) |

**Приёмка на реальной БД:** InMemory ≠ доказательство. Локальный PG на машине агента
не поднят (нет Docker Desktop). Воспроизведение: `tools/date_op_pg/run_integration.ps1`
или workflow `date-op-pg`.

## Существующие транзакционные механизмы (проверка)

1. **psycopg `connection.transaction()` + `SELECT … FOR UPDATE`** — используется в
   `PostgresPeriodDateStore` для date-op и snapshot. Миграция не обязательна для CAS
   по `updated_at`, если все writers идут через этот store.
2. **Supabase JS/PostgREST upsert** — отдельный HTTP-запрос; общего BEGIN с
   `access_audit.insert` нет. **Недостаточен.**
3. **Готовой SQL-функции/RPC** для period date correction в миграциях **нет.**

## Минимальное предложение на отдельное согласование (НЕ применять)

Цель: один RPC/SQL entrypoint, недоступный «случайный» PostgREST overwrite,
жёсткий ledger `operation_id`.

```sql
-- НЕ ПРИМЕНЯТЬ без отдельного разрешения владельца.

alter table public.case_pipeline_data
  add column if not exists pipeline_revision bigint not null default 1;

alter table public.case_pipeline_data
  add column if not exists period_date_operations jsonb not null default '{}'::jsonb;

create or replace function public.apply_period_date_correction(
  p_case_id uuid,
  p_operation_id text,
  p_collection text,
  p_period_id text,
  p_field text,
  p_new_value text,
  p_expected_revision bigint,
  p_reason text,
  p_actor_id text,
  p_value_source text default 'staff_verified'
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
-- одна транзакция: lock row, check op_id, CAS revision, mutate, audit embed,
-- write period_date_operations[p_operation_id], bump revision, return event
$$;

create or replace function public.save_pipeline_snapshot_cas(
  p_case_id uuid,
  p_expected_revision bigint,
  p_payload jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
-- FOR UPDATE; reject stale revision; merge staff_date_correction; bump revision
$$;

revoke all on function public.apply_period_date_correction from public, anon, authenticated;
grant execute on function public.apply_period_date_correction to service_role;
revoke all on function public.save_pipeline_snapshot_cas from public, anon, authenticated;
grant execute on function public.save_pipeline_snapshot_cas to service_role;
```

### План отката

1. `drop function` обеих RPC.
2. `alter table … drop column period_date_operations, drop column pipeline_revision`
   (после проверки, что приложение не пишет в них).
3. Вернуть writers на предыдущий код (git revert PR).

### Риски миграции

- Короткий lock на строку `case_pipeline_data` при пике pipeline.
- Нужен cutover всех snapshot-writers на RPC (иначе обход).
- Не трогает prod-данные дат до вызова операции.

## Инварианты (целевые)

- Ошибка аудита / фиксации op_id → rollback даты.
- Success ack только после commit.
- Повтор op_id → прежний результат; другой payload → конфликт.
- Snapshot со старой ревизией → conflict, не слепой upsert.
- Подтверждение даты ≠ перерасчёт пенсии / draft / доставка.

## Рекомендация владельцу

1. **Не merge #268** как «атомарность доказана», пока нет зелёного PG integration.
2. Решить: достаточно ли psycopg-CAS в приложении **или** нужен RPC из блока выше
   (отдельное OK на миграцию).
3. Поднять локальную/CI тестовую БД и прогнать
   `tests/integration/test_period_date_correction_pg.py` (+ сценарии A–B на двух
   соединениях).
