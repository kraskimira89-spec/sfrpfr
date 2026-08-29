# Техдолг по логам API (2026-08-29)

Источник: `/var/log/sfrfr/api.err`, `/var/log/sfrfr/api.log`, `journalctl -u sfrfr-api`.

## Классификация

| Код / симптом | Частота | Статус | Действие |
|---|---|---|---|
| `orders.paid_at does not exist` (42703) | 18 в истории | **исправлено в коде** (select без `orders.paid_at`; колонка есть в `payments`) | Не чинить код. Очистить из журналов. |
| `case_messages_case_id_fkey` (23503) | 16, последний 2026-08-29 12:40 | **живо** | Фантомный `case_id` (есть в локальном store/intake, нет в Postgres). Не пытаться insert; буфер по `max_user_id`. |
| `checklist_items_case_id_fkey` | 1 | тот же корень | После фикса фантомов не должно повторяться. |
| `ensure_case_supabase_timeout_or_error` | 1 | редкий | Оставить как есть (таймаут 5с + буфер). |
| HTTP 500 в `api.log` | старые access-строки | после деплоя ~20:15 — только 200 | Журнал access не ротировался; truncate после фикса. |
| journalctl `-p err` за 48ч | 0 | ок | — |

Орфаны (нет в `cases`):

- `41935a1d-…` (13 warnings) — в `cases.json` + `max_intake.json`
- `a8e4f1cc-…`, `04901cf1-…`

## План техдолга (приоритет)

1. **P0** — не резолвить фантомный `intake.case_id` / local id без проверки в Supabase.
2. **P0** — при логировании документов/чеков всегда передавать `max_user_id` для буфера.
3. **P1** — ops: сбросить фантомные `case_id` в `max_intake.json` на VPS.
4. **P1** — ротация/очистка `api.err` + truncate хвоста `api.log` после подтверждения.
5. **P2** (не сейчас) — миграция `orders.paid_at` опционально для удобства; не нужна для работы.

## Критерии готовности

- Нет новых `case_messages_case_id_fkey` / `paid_at` в `api.err` после деплоя.
- Клиентский текст/PDF/чек при фантоме уходит в `max_chat_pending`, не теряется.
- Существующие дела с реальным UUID в Supabase работают как раньше.
