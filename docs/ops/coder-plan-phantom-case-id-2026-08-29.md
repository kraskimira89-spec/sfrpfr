# План кодера: фантомный case_id → FK case_messages

Связан с [tech-debt-api-logs-2026-08-29.md](./tech-debt-api-logs-2026-08-29.md).

## Шаги — статус

1. ✅ `_case_id_for_max_user`: проверка `_case_exists_in_supabase`, сброс фантома.
2. ✅ `_ingest_bytes`: `max_user_id` + `_chat_case_id`.
3. ✅ Все вызовы `_ingest_bytes` прокидывают `user_id`.
4. ✅ Тесты: phantom / real / `_chat_case_id` / exclusive `bind_max`.
5. ✅ VPS: очистка intake + truncate логов.

## Дополнение (после сверки плана)

- ✅ `_chat_case_id(preferred)` — единая точка для ленты и `_reply` (не писать фантом, даже если caller передал local id).
- ✅ Свободный текст / `/documents` — через `_chat_case_id`, не сырой intake/record.
- ✅ `CaseStore.bind_max` exclusive + `clear_max_binding` при phantom в `ensure_case`.

## Не делать

- Не добавлять колонку `orders.paid_at` без отдельного ТЗ.
- Не удалять локальные записи `cases.json` (могут быть uploads) — только сброс intake / MAX-binding.
- Не ломать happy-path с валидным supabase case_id.
