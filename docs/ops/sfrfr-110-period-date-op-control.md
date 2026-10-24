# SFRFR-110: контрольная точка — точечная операция исправления даты

**Ветка:** `feat/sfrfr-110-period-date-correction` (PR #268).
**Auto-merge OFF.** Merge / deploy / RPC-миграция / live / E01-wire / close SFRFR-110 — **не** этим отчётом.

Атомарная граница: `docs/ops/sfrfr-110-period-date-atomic-boundary.md`.

## Контракт

```text
BEGIN (psycopg)
  FOR UPDATE case_pipeline_data
  check operation_id (latest + staff_date_corrections[]) / expected_version / period_id
  mutate field + embed period_date_corrected + append history + dependents needs_recheck
  CAS updated_at
COMMIT
→ ack только после commit
```

Snapshot writers того же контура: тот же FOR UPDATE + merge corrections + CAS
(`PostgresPeriodDateStore.save_pipeline_snapshot`).
Отсутствие ключа periods ≠ запись `[]`.

## Воспроизведение PG (local)

```powershell
# Требует Docker engine. Порт 15433, БД sfrfr_date_op_test — не prod.
.\tools\date_op_pg\run_integration.ps1
```

Вручную:

```powershell
docker compose -f tools/date_op_pg/docker-compose.yml up -d --wait
$env:DATABASE_URL='postgresql://sfrfr:sfrfr_test@127.0.0.1:15433/sfrfr_date_op_test'
.\.venv\Scripts\python.exe tools\date_op_pg\bootstrap_schema.py
.\.venv\Scripts\python.exe -m pytest tests/integration/test_period_date_correction_pg.py -q --basetemp=tmp/pytest-date-op-pg
```

Схема: `tools/date_op_pg/schema_minimal.sql` (колонки из версионированных миграций, без auth/RLS/prod-данных).

## CI

Workflow: `.github/workflows/date-op-pg.yml` — service `postgres:16`, bootstrap + unit + integration.

## SHA / CI evidence

| Поле | Значение |
|---|---|
| HEAD | `4581ac17` (docs whitespace; harness в `49dcf06c`) |
| CI `date-op-pg` | **success** — https://github.com/kraskimira89-spec/sfrpfr/actions/runs/40107542269 |
| Unit + Integration на CI | Bootstrap schema + InMemory + psycopg — зелёные |

## Локальный статус среды (агент, 2026-10-24)

| Проверка | Результат |
|---|---|
| Docker Desktop / docker engine | **Нет:** `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`; `Docker Desktop.exe` не найден |
| Локальный `psql` / служба Postgres | **Нет** |
| Unit InMemory (агент) | **20 passed** |
| Integration PG (агент) | **12 skipped** (нет Docker) |
| Integration PG (CI) | **пройден** (run выше) |

## Тесты

```text
Unit (InMemory, A–E + history):
  .\.venv\Scripts\python.exe -m pytest tests/unit/test_period_date_correction.py -q --basetemp=.tmp_pytest_date_op

Integration PG (обязательные сценарии ТЗ):
  tests/integration/test_period_date_correction_pg.py
  → локально: SKIP без Docker; CI: date-op-pg success
```

## Перечень writers затрагиваемых полей

| Путь | Поля | Конкурентность | Статус |
|---|---|---|---|
| `PostgresPeriodDateStore.apply_correction` | ils/labor periods, findings, draft, updated_at | FOR UPDATE + CAS | OK |
| `PostgresPeriodDateStore.save_pipeline_snapshot` | snapshot merge + CAS | FOR UPDATE + CAS | OK |
| `CaseRepository.save_pipeline_snapshot` | делегирует в store | через store | OK |
| `admin_portal.review_discrepancy` | findings | **был** PostgREST upsert → **переведён** на `save_pipeline_snapshot` | OK (узкий фикс) |
| `admin_portal` / `portal` `get` pipeline | read-only | — | OK |
| Прямой PostgREST/SQL клиент вне store | любые колонки строки | **нет CAS** | **Блокер выпуска**, пока нет RPC/revoke table write |
| `case_store.py` (локальный файловый) | не PG | — | вне контура |

**Вывод по PostgREST:** успешные PG-тесты store **не** закрывают обход другим writer с service_role. Узкий фикс findings-upsert сделан. Полное закрытие обхода — RPC + revoke (отдельное разрешение на миграцию).

## Embedded-аудит

| Требование | Реализация |
|---|---|
| История не затирается | `staff_date_corrections[]` append + `staff_date_correction` = latest |
| Snapshot merge | `merge_periods_preserve_corrections` по `period_id` |
| before/after, actor, basis, versions, op_id | в `PeriodDateCorrectedEvent.as_dict()` |
| Старый op_id находимый | `lookup_by_operation_id` ищет history |
| Подтверждение из сохранённого | `IDEMPOTENT_REPLAY` / `reconcile_unknown` |
| Лимит JSON | явного hard-cap нет; риск роста массива на периоде — остаток; ledger-колонка = отдельная миграция |

Один маркер `staff_date_correction` **не** считается полным ledger; history-массив — промежуточное доказательство без DDL.

## E/F / приоритет

| ID | Статус |
|---|---|
| E01 write-op | Код + **CI PG success**; локальный Docker у агента отсутствует; E01-wire нет |
| Close SFRFR-110 | нет |
| Зависимость precheck #269 | **нет** — precheck только читает периоды / пишет findings precheck, не канонические даты |

## Рекомендация

1. PG evidence через CI получен (`date-op-pg` success). Остаётся блокер PostgREST service_role вне store.
2. RPC-миграцию **не** применять без отдельного OK.
3. Merge #268 — только отдельным разрешением (не закрывает SFRFR-110 / E01-wire).
4. Precheck (#269) продолжать независимо.
