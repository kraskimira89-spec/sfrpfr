# Отчёт изоляции + harness (цикл 5)

## Контракт

```text
PRECHECK_PG_DSN       — единственный DSN (без DATABASE_URL / PRECHECK_PROBE_*)
PRECHECK_TEST_RUN_ID  — владелец стенда (precheck_test_guard.environment)
Цель: 127.0.0.1:55432 / sfrfr_precheck / user sfrfr
```

PG-harness ≠ полная схема Supabase приложения. PostgREST `:55433` — отдельный набор тестов.

## Результат ворот (после фикса контракта)

```text
SHA: e3209b6657e2d88e5c089a75aac64a5d79ae4cca
Идентификатор: cycle5-iso-gate-469caed7
Компоненты:
  - probe → PRECHECK_PG_DSN (JSON PASS)
  - pytest isolation + job_pg + job_postgrest → 21 passed
  - PostgREST up
  - guard до TRUNCATE в фикстурах
Проверки отказов: DATABASE_URL-only, prod host, foreign run_id, read-only
Результат: PASS
Изменяющие запросы до подтверждения: отсутствуют
Код probe: 0 · gate: 0 · pytest: 0
Логи: tmp/cycle5/db-probe.log, docs/ops/logs/sfrfr-111-db-probe-contract.jsonl
```

Статическая рецензия со старым `DATABASE_URL` fallback — устаревший снимок; на ветке #269 снят.

## Browser

| Пункт | Статус |
|---|---|
| Playwright skeleton | `apps/admin/e2e/precheck.spec.ts` + config (исключены из tsc) |
| Зависимость Playwright | не закреплена в package.json — добавить перед CI E2E |
| GoTrue / staff JWT | **BLOCKED** |
| Критерий | не снижаем |

## Оговорки имён тестов

- `test_two_handlers_only_one_claims` — два последовательных claim, не параллельные процессы.
- Notify-retry в PG suite может ставить флаг вручную — не путать с live MAX enqueue.

Merge / deploy / live MAX / платежи — нет.
