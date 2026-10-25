# Реестр тестов SFRFR-111 / PR #269

**Код под тестом (полный SHA):** `b90fb167af315811368140315cfc8e44e95a2d37`  
**Ветка:** `feat/sfrfr-primary-doc-precheck`  
**Дата прогона:** 2026-10-25  
**Окружение:** Windows · `.venv` · Docker precheck harness `127.0.0.1:55432/sfrfr_precheck` + PostgREST `:55433` · `PRECHECK_TEST_RUN_ID=precheck_94b32e8c626544e08efc7ebe65f3c264`

Не суммировать наборы в одну цифру «83/84 passed».

| # | Набор | Команда | Результат | Сырой лог |
|---|---|---|---|---|
| 1 | unit guard | `python -m pytest tests/unit/test_precheck_isolation_guard.py -q` | **15 passed** (exit 0) | `docs/ops/logs/sfrfr-111-registry-unit-guard-20261025-105507-b90fb167.txt` |
| 2 | neg: чужой run → нет TRUNCATE | `python -m pytest tests/integration/test_precheck_guard_no_truncate.py -q` | **1 passed** (exit 0) | `docs/ops/logs/sfrfr-111-registry-neg-no-truncate-20261025-105507-b90fb167.txt` |
| 3 | read-only probe | `python tools/precheck_db_probe.py` | **PASS** JSON (exit 0) | `docs/ops/logs/sfrfr-111-registry-probe-20261025-105507-b90fb167.txt` |
| 4 | PG PgRestShim | `python -m pytest tests/integration/test_precheck_job_pg.py -q` | **7 passed** (exit 0) | `docs/ops/logs/sfrfr-111-registry-pg-shim-20261025-105507-b90fb167.txt` |
| 5 | PostgREST HTTP | `python -m pytest tests/integration/test_precheck_job_postgrest.py -q` | **3 passed** (exit 0) | `docs/ops/logs/sfrfr-111-registry-postgrest-20261025-105507-b90fb167.txt` |
| 6 | isolation gate | `python tools/precheck_job_pg/run_isolation_gate.py` | **RESULT: PASS** (exit 0) | `docs/ops/logs/sfrfr-111-registry-gate-20261025-105507-b90fb167.txt` |

## CI GitHub на этом head

| SHA | check-runs |
|---|---|
| `b65e48f9` | success (последний зелёный CI на ветке) |
| `6c6e1d1d` … `b90fb167` | **0** check-runs; причина доставки не установлена; empty retrigger — ошибка процесса |

Дифф после зелёного CI: только docs/ops + `scripts/dbhub-supabase-selfhost.toml` (см. journal).

## Browser / Auth

Пока **не** в реестре как passed: нет изолированного staff Auth. Skeleton `apps/admin/e2e/precheck.spec.ts` при отсутствии env делает `skip` — для приёмки будет заменён на явный BLOCKED (следующий этап).
