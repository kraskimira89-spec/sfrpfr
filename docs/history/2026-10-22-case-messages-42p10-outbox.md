# 2026-10-22: 42P10 на INSERT case_messages (outbox ON CONFLICT)

## Симптом

После #190/#191 счёт и MAX pay-link работают, но insert в `case_messages`
для тестового дела падал с Postgres **42P10** (`ON CONFLICT` / unique index
mismatch). Pay-текст в ленту кабинета мог не писаться; в MAX уходил через
fallback (#191).

## Причина

Триггер `AFTER INSERT ON case_messages` → `private.enqueue_case_chat_outbox()`
делал:

```sql
on conflict (message_id) do nothing;
```

Уникальный индекс — **partial**:

```sql
case_chat_outbox_message_uidx ON (message_id) WHERE message_id IS NOT NULL
```

Без predicate Postgres не находит matching constraint → 42P10, откат всего
INSERT (для `channel_origin` in `cabinet` / `admin` / `bot`).

## Фикс

PR #192: `ON CONFLICT (message_id) WHERE message_id IS NOT NULL DO NOTHING`
(миграция `20261022120000_fix_enqueue_outbox_on_conflict.sql`).

На prod (Reg.ru self-host) миграция применена через `supabase_admin` в
`supabase-db` (роль `postgres` там не superuser).

## Проверено

- unit: `test_enqueue_case_chat_outbox_on_conflict.py` + `test_pay_link.py`
- read-only SQL: индекс partial; после apply — `HAS_WHERE_PRED True`
