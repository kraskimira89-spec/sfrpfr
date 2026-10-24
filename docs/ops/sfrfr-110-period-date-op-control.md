# SFRFR-110: контрольная точка — точечная операция исправления даты

**База PR:** `origin/main` (`eea343e3…`, канон #262).
**Не** база #267 / стек #261–#266.
**Auto-merge OFF.** Merge / deploy / миграции / live / E01-wire / close — не этим отчётом.

Атомарная граница и стоп: `docs/ops/sfrfr-110-period-date-atomic-boundary.md`.

## Контракт

```text
BEGIN (psycopg)
  FOR UPDATE case_pipeline_data
  check operation_id / expected_version / period_id
  mutate field + embed period_date_corrected + dependents needs_recheck
  CAS updated_at
COMMIT
→ ack только после commit
```

Snapshot writers того же контура: тот же FOR UPDATE + merge + CAS
(`PostgresPeriodDateStore.save_pipeline_snapshot`).
`CaseRepository.require_case_exact` — без staff-remap для write.

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

Нет публичного HTTP / MAX / E01-wire.

## Write-пути

| Путь | Изменение |
|---|---|
| `PostgresPeriodDateStore.apply_correction` | Date-op CAS |
| `PostgresPeriodDateStore.save_pipeline_snapshot` | Snapshot CAS |
| `CaseRepository.save_pipeline_snapshot` | Делегирует в psycopg CAS (не PostgREST upsert) |
| `CaseRepository.require_case_exact` | Точный case_id |

## Тесты

```text
Unit (InMemory, в т.ч. A–E snapshot):
  .\.venv\Scripts\python.exe -m pytest tests/unit/test_period_date_correction.py -q --basetemp=.tmp_pytest_date_op
  → 19 passed

Integration PG:
  → SKIP / не доказано (database_reachable=False)
```

## E/F

| ID | Статус |
|---|---|
| E01 write-op | Код есть; **приёмка на PG не доказана**; E01-wire нет |
| Close SFRFR-110 | нет |

## Остаточные риски

1. Нет зелёного PG concurrent evidence.
2. Прямой PostgREST/другие clients в обход store.
3. Ledger op_id только в JSON периода (RPC/колонка — на согласование).
4. Нет job/HTTP wiring.

## Рекомендация

**Не принимать #268 как закрытие атомарности** до PG-доказательств и решения
по RPC-миграции. Merge только отдельным разрешением.
