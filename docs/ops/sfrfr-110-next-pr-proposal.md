# Минимальный следующий PR (после #263)

## Рекомендация: **без миграции**

```text
feat(SFRFR-110): audit period-date write paths + E01 operation event draft
```

### Цель

Закрыть контракт E01 на уровне **инвентаризации write-путей и черновика события**,
без объявления «дата исправлена» в клиентском MAX.

### Включить

1. Read-only отчёт: где код пишет/может писать даты периодов (`ils_periods` / findings / staff).
2. Черновик payload события `period_date_corrected` (before/after/reason/actor/source/version).
3. Тесты контракта: `persist_flag_is_trusted` отвергает LLM; `ok=None` → запрет E01-фразы.
4. Ссылка на `docs/ops/sfrfr-110-e01-operation-contract.md`.

### Не включать

- Миграции БД.
- Production TrustedErrorContext adapter с долговременным хранилищем.
- Wire E01 в MAX reply-path.
- Исправления всех callback из карты.
- Merge #261/#263, deploy, live.

### Когда нужна отдельная миграция

Только если audit покажет невозможность version/before-after в существующих
audit/JSON полях без потери конкурентной безопасности — тогда **второй** PR
с обоснованием схемы, отдельным согласованием.

## Альтернатива (уже почти закрыта доками)

Если audit писать нельзя до merge #261 — ограничиться docs-only PR поверх #263:
дожать callback subcodes `intake:*`/`q:*` и пост-фильтр LLM критических фраз
как **отдельную** узкую задачу после Null-проверки.

Приоритет владельца: **E01 storage contract audit (без миграции)** → затем
минимальный wire E01 при наличии реального ack.
