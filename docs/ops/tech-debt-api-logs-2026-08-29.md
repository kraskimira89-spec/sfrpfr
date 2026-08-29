# Техдолг по логам API (2026-08-29)

Источник: `/var/log/sfrfr/api.err`, `/var/log/sfrfr/api.log`, `journalctl -u sfrfr-api`.

## Классификация

| Код / симптом | Частота | Статус | Действие |
|---|---|---|---|
| `orders.paid_at does not exist` (42703) | 18 в истории | **закрыто** | select без `orders.paid_at`; журналы очищены |
| `case_messages_case_id_fkey` (23503) | 16 | **закрыто в коде** | `_chat_case_id` + буфер; фантомы intake/local unbound |
| `checklist_items_case_id_fkey` | 1 | тот же корень | не должен повторяться |
| `ensure_case_supabase_timeout_or_error` | 1 | редкий | без изменений (таймаут + буфер) |
| HTTP 500 в `api.log` | старые | **очищено** | truncate после деплоя |
| journalctl `-p err` | 0 | ок | — |

## План техдолга — статус

1. **P0** ✅ не резолвить фантомный `intake` / local id без проверки в Supabase (`_chat_case_id`, `_case_id_for_max_user`).
2. **P0** ✅ документы/чеки всегда с `max_user_id` для буфера.
3. **P1** ✅ ops: сброс фантомов в `max_intake.json` на VPS.
4. **P1** ✅ ротация `api.err` / `api.log` (бэкап в `/var/log/sfrfr/archive/`).
5. **P2** (не сейчас) — миграция `orders.paid_at`.

## Критерии готовности

- [x] Нет новых `case_messages_case_id_fkey` / `paid_at` в `api.err` после деплоя.
- [x] При фантоме текст/PDF → `max_chat_pending`.
- [x] Реальный UUID в Supabase — как раньше.
