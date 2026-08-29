# План кодера: фантомный case_id → FK case_messages

Связан с [tech-debt-api-logs-2026-08-29.md](./tech-debt-api-logs-2026-08-29.md).

## Шаги

1. `_case_id_for_max_user` (`handler.py`):
   - после fallback на `intake.case_id` проверить `_case_exists_in_supabase`;
   - если нет — обнулить `intake.case_id`, `save`, вернуть `None` (сообщения → буфер).
2. `_ingest_bytes`: добавить `max_user_id`, передавать в `append_case_chat_message`.
3. Все вызовы `_ingest_bytes` — прокинуть `user_id`.
4. Тест: фантомный intake id не возвращается; при FK + mid — буфер.
5. На VPS после деплоя: очистить фантомы в intake (скрипт/one-liner), `truncate -s 0 /var/log/sfrfr/api.err`, truncate `api.log` или `>`.

## Не делать

- Не добавлять колонку `orders.paid_at` без отдельного ТЗ.
- Не удалять локальные записи `cases.json` (могут быть uploads) — только сброс intake id.
- Не ломать happy-path с валидным supabase case_id.
