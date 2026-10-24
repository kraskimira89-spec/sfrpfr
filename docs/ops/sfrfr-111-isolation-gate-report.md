# Отчёт изоляции + harness (цикл 5)

## Контракт

```text
PRECHECK_PG_DSN       — единственный DSN (без DATABASE_URL / PRECHECK_PROBE_*)
PRECHECK_TEST_RUN_ID  — владелец стенда (precheck_test_guard.environment)
Цель: 127.0.0.1:55432 / sfrfr_precheck / user sfrfr
```

Канон кода: `tools/precheck_job_pg/isolation_guard.py`  
Маркер создаёт только `up.ps1`. Фикстуры / probe / worker — только `require_test_target` + `verify_test_connection`.

PG-harness ≠ полная схема Supabase приложения. PostgREST `:55433` — отдельный набор тестов.

## Результат ворот (после isolation_guard)

```text
SHA: 65b6881a
Компоненты:
  - isolation_guard unit → 16 passed
  - probe → JSON PASS (read_only, columns staff_document_check_jobs)
  - pytest job_pg + guard_no_truncate → 8 passed
  - PostgREST → 3 passed
  - full precheck suite → 83 passed
  - run_isolation_gate.py → RESULT: PASS
Проверки отказов: DATABASE_URL-only, wrong host/port/db/user, foreign run_id, read-only write
Изменяющие запросы до подтверждения изоляции: отсутствуют
Лог suite: docs/ops/logs/sfrfr-111-cycle5-full-precheck-20261024-215447-65b6881a.txt
```

## Browser

| Пункт | Статус |
|---|---|
| Playwright skeleton | `apps/admin/e2e/precheck.spec.ts` + config (исключены из tsc) |
| GoTrue / staff JWT | **BLOCKED** |
| API smoke скрипт | `tools/precheck_e2e/staff_document_check_api_smoke.py` (нужны PRECHECK_E2E_*) |
| Критерий | не снижаем |

## Оговорки имён тестов

- `test_two_handlers_only_one_claims` — два последовательных claim, не параллельные процессы.
- Notify-retry в PG suite может ставить флаг вручную — не путать с live MAX enqueue.

Merge / deploy / live MAX / платежи — нет (запрет ТЗ SFRFR-111 без отдельного OK).
