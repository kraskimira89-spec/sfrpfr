# 2026-08-29 — Миграция loss_reason на prod

Применено на VPS (Postgres `/opt/sfrfr/.env` DATABASE_URL):

- `cases.loss_reason text`
- `cases.closed_at timestamptz`
- запись в `sfrfr_ops.schema_migrations`

Файл: `supabase/migrations/20260829190000_cases_loss_reason.sql`  
Связано: SFRFR-25, playbook-staff-cabinet-crm.
