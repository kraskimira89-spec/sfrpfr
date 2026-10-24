# Отчёт изоляции precheck (цикл 5)

> Статическая рецензия Стратега со ссылкой на `DATABASE_URL` fallback относилась к **устаревшему** снимку probe. На ветке #269 fallback уже снят (`refuse_if_not_isolated`, без чтения `DATABASE_URL`).

## Результат ворот

```text
SHA: 469caed7b2bb2c895e52ae3b5aea501ca8977a6a
Идентификатор тестового запуска: cycle5-iso-gate-469caed7
Компоненты и фактические цели подключения:
  - probe/psycopg → PRECHECK_PG_DSN → 127.0.0.1:55432 / sfrfr_precheck / user sfrfr
  - PostgREST → http://127.0.0.1:55433 (up)
  - DATABASE_URL: игнорируется (neg: only DATABASE_URL → refuse)
Проверки защитных отказов:
  - neg_database_url_only PASS
  - neg_prod_host PASS
  - neg_wrong_dbname PASS
  - connected_identity + marker PASS
  - read_only_session PASS (ReadOnlySqlTransaction)
  - run_id_owned PASS
  - neg_foreign_run_cleanup PASS
  - probe_cli PASS
Результат: PASS
Причина: —
Изменяющие запросы до подтверждения изоляции: отсутствуют
Код завершения gate: 0
Сырой лог: docs/ops/logs/sfrfr-111-isolation-gate-469caed7.txt
```

Команда:

```powershell
$env:PRECHECK_PG_DSN='postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck'
$env:PRECHECK_TEST_RUN_ID='cycle5-iso-gate-469caed7'
.\.venv\Scripts\python.exe tools\precheck_job_pg\run_isolation_gate.py
```

Единый DSN: `PRECHECK_PG_DSN` ↔ `PRECHECK_PROBE_DATABASE_URL` (синонимы в `resolve_test_dsn`).

## Browser E2E

| Пункт | Статус |
|---|---|
| Изоляция стенда PG/PostgREST | PASS |
| Admin UI login (GoTrue JWT) | **BLOCKED** — Auth не в стенде |
| API enqueue через PostgREST | PASS (отдельные тесты) |
| Полный browser сценарий B | BLOCKED (зависит от login) |

Критерий browser не снижаем. Merge/deploy/live/платежи — нет.
