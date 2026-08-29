# 2026-08-29 — Логи API: фантомный case_id и очистка журналов

## Аудит

- `orders.paid_at` — исторические 500, в коде уже не выбирается; колонка в `payments` есть.
- Живой шум: `case_messages_case_id_fkey` из intake/store UUID без строки в Postgres.

## Фикс

- `_case_id_for_max_user` сбрасывает фантомный intake id.
- `_ingest_bytes` пишет в ленту с supabase id + `max_user_id` для буфера.
- FK → буфер логируется как info.

Планы: `docs/ops/tech-debt-api-logs-2026-08-29.md`, `docs/ops/coder-plan-phantom-case-id-2026-08-29.md`.
