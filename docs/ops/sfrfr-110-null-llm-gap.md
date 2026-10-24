# Пробел Null → LLM и статус постфильтра

## Формулировка покрытия

> Политический E05/F04-путь проверен изолированно.

После PR постфильтра (`max_llm_action_claim_filter`, срез 1):

> Неподтверждённые completed-action claims из ограниченного списка
> на пути `max_llm_reply` блокируются. Запрет неподтверждённых утверждений
> **во всех** MAX-ответах (callback, rule-bot, staff) по-прежнему не доказан.

## Было (до фильтра)

```text
Null → max_llm_reply → «исправлено» могло уйти (prompt-only)
```

## Стало (срез 1)

```text
Null → max_llm_reply → filter_llm_action_claims → safe fallback
Пустой policy-text → LLM → тот же фильтр
```

Документ фильтра: `docs/ops/sfrfr-110-max-llm-action-claim-filter.md`.

## Доставка (без смешения)

| Ситуация | Смысл |
|---|---|
| `enqueue_failed` / `FAILED_BEFORE_OR_AT_SEND` | Установленный отказ до/на send **только если** код это явно зафиксировал; exception/timeout ≠ доказательство «записи точно не было» |
| `UNKNOWN_AFTER_ACCEPT` | Транспорт мог принять, persist статуса не подтверждён — не слепой retry |
| Согласованный policy-текст при прямом fallback | Не доказывает отсутствие дубля при неизвестном исходе enqueue |
