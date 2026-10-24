# Минимальный следующий PR (после #263)

## Статус

Оформлен audit PR:

```text
docs(SFRFR-110): audit period-date write paths and draft correction event
```

Ветка: `docs/sfrfr-110-e01-period-date-audit` (base = #263).

Канон аудита: `docs/ops/sfrfr-110-period-date-write-audit.md`.

### Итог аудита о миграции

Данных для E01-wire пока недостаточно (нет точечной операции).  
Целевой минимум после появления операции — **код без миграции** (JSON version +
audit payload). Отдельная миграция — только если JSON version окажется небезопасен.

### Не включать (и не включено)

- Миграции БД; production adapter; wire E01; правки всех callback.
- Merge #261/#263, deploy, live.

### Следующий узкий PR после audit (не этот)

Пост-фильтр критических утверждений на `max_llm_reply` при Null
(`docs/ops/sfrfr-110-null-llm-gap.md`) — отдельно от записи даты.
