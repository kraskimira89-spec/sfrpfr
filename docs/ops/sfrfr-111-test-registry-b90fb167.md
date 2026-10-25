# Реестр прогонов SFRFR-111 (последние принимаемые)

Без смешивания: каждая строка = один запуск.

## Unit guard

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `pytest tests/unit/test_precheck_isolation_guard.py tests/unit/test_precheck_db_isolation.py -q` |
| Итог | **16 passed** |
| Окружение | `.venv` без harness |
| Лог | terminal |

## PG integration (PgRestShim)

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `pytest tests/integration/test_precheck_job_pg.py tests/integration/test_precheck_guard_no_truncate.py -vv` |
| Итог | **8 passed** |
| Harness | `tools/precheck_job_pg/up.ps1` → `:55432` |
| Маркер run | `precheck_94b32e8c626544e08efc7ebe65f3c264` |

## PostgREST HTTP

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `pytest tests/integration/test_precheck_job_postgrest.py -q` |
| Итог | **3 passed** |
| Harness | `:55433` (postgrest/postgrest:v12.2.8) |

## Probe

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `python tools/precheck_db_probe.py` |
| Итог | JSON `PASS`, read_only, 16 columns |
| Run | тот же harness |

## Isolation gate

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `python tools/precheck_job_pg/run_isolation_gate.py` |
| Итог | **RESULT: PASS** (neg DATABASE_URL, foreign run, read-only) |

## Full precheck suite (одной командой)

| Поле | Значение |
|---|---|
| SHA | `65b6881a` |
| Команда | `pytest unit(guard/db_isolation/primary_doc/lifecycle/handler) + integration(job_pg + guard_no_truncate + job_postgrest)` |
| Итог | **83 passed** |
| Лог | `docs/ops/logs/sfrfr-111-cycle5-full-precheck-20261024-215447-65b6881a.txt` |

## CI

| Поле | Значение |
|---|---|
| SHA | `b65e48f9` (последний с runs) |
| Run | `40114041028` |
| Итог | api/cabinet/admin SUCCESS |
| Замечание | docs-only commit; head PR сейчас `3116e0d9`, CI gap — см. `sfrfr-111-ci-gap-2026-10-25.md` |

## Не запущено

- Browser E2E (GoTrue login) — блокер, не skip.
