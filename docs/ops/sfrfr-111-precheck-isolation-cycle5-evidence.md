# SFRFR-111 cycle 5 — изоляция + сырой лог (не реконструкция)

**Дата:** 2026-10-24  
**PR:** #269 `feat/sfrfr-primary-doc-precheck`  
**Merge / deploy / live MAX / prod-миграции:** нет

## 1. Сырой pytest (новый прогон)

| Поле | Значение |
|---|---|
| Полный SHA | `fe1188210279a7f22b1c253338f6e0cf74e35e5c` |
| Ветка | `feat/sfrfr-primary-doc-precheck` |
| Время (UTC) | `2026-10-24T16:18:11Z` |
| Python | `3.14.5` (`.venv`) |
| Окружение | Windows; `PRECHECK_PG_DSN` set; `DATABASE_URL` unset |
| Команда | см. сырой лог |
| Итог | **70 passed**, 0 failed, exit **0** |
| Сырой лог | `docs/ops/logs/sfrfr-111-isolation-pytest-20261024-211811-fe118821.txt` |
| JUnit | `docs/ops/logs/sfrfr-111-isolation-junit-20261024-211811-fe118821.xml` |

Набор: handler routing + lifecycle + primary + staff_document_check + **isolation negatives**.

Предыдущий документ hardening (`091fe846` / «61 passed») **не** переписывался задним числом. Этот прогон — отдельный артефакт на SHA `fe118821…`.

Первый неудачный прогон без `--basetemp` (PermissionError Temp) сохранён отдельно:  
`docs/ops/logs/sfrfr-111-hardening-pytest-20261024-211753-fe118821.txt` — exit 1; не использовать как зелёный.

## 2. Изоляция БД (исправления)

| Требование | Статус |
|---|---|
| Только тестовый DSN | `PRECHECK_PG_DSN` / `PRECHECK_PROBE_DATABASE_URL` |
| Без fallback на `DATABASE_URL` | да — probe exit 2 при только `DATABASE_URL` |
| Allowlist db/user/host | `sfrfr_precheck` / `sfrfr` / localhost\|127.0.0.1\|precheck-pg |
| Маркер в БД | `public.sfrfr_test_isolation` = `sfrfr_precheck_isolation_ok` |
| Read-only probe | `SET default_transaction_read_only = on` |
| Санитизация исключений | `_sanitize_exc_message` |
| Negative unit | `tests/unit/test_precheck_db_isolation.py` |

Код: `tools/precheck_job_pg/isolation.py`, `tools/precheck_db_probe.py`, schema marker.

### Probe (после фикса SET)

```text
RESULT: ok
identity: database=sfrfr_precheck user=sfrfr marker=sfrfr_precheck_isolation_ok
columns: 16 (staff_document_check_jobs)
```

Отрицательный: только `DATABASE_URL` → `RESULT: isolation_refused missing_precheck_probe_database_url` (exit 2).

### PG integration (тот же DSN + marker)

| Поле | Значение |
|---|---|
| SHA | `fe1188210279a7f22b1c253338f6e0cf74e35e5c` |
| Лог | `docs/ops/logs/sfrfr-111-pg-isolation-pytest-20261024-211833-fe118821.txt` |
| Итог | **7 passed**, exit **0** |

Путь доступа по-прежнему **PgRestShim** (тот же table/update/eq CAS). Полноценный PostgREST-контейнер приложения **не** поднят — открытый остаток приёмки.

## 3. Live Трекер (MCP, не карта)

Срез `issues_find` 2026-10-24 ~16:18Z UTC:

| Задача | Статус |
|---|---|
| SFRFR-100 | Открыт |
| SFRFR-110 | Открыт |
| SFRFR-111 | Открыт (assignee пуст в issue_get) |
| SFRFR-112…117 | Открыт |

Hardening/изоляция **не** закрывают тикеты.

## 4. Незакрытые требования цикла «изолированная интеграционная приёмка»

| # | Требование | Статус |
|---|---|---|
| A | PostgREST-путь приложения (не только shim) | открыто |
| B | Process restart отдельными процессами (часть сценариев есть в PG suite) | частично |
| C | Browser smoke live staff UI | открыто |
| D | Полный upload/answer/order (не cabinet-stub) | частично |
| — | Merge / deploy / live MAX | запрещено |

## 5. CI #269

На момент фиксации evidence: последние runs `api`/`cabinet`/`admin` по ветке — **success** (см. `gh run list`).

Приёмку не закрывать.
