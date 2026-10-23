# 2026-10-23 — SFRFR-93: not_required + dry-run timer

## Решение по кандидатам

| Группа | Действие | Tracker |
|--------|----------|---------|
| 2× 1₽ smoke (`c05f1cfc`, `d5d29b06`) | `fiscal_status=not_required` (по одной строке) | SFRFR-98 |
| 2× pending (чужой shop / access denied) | оставить в окне на dry-run | SFRFR-99 |
| 7× NULL + succeeded receipt | без правок (gate → registered в бою) | — |

## Схема

- Миграция `20261023190000_payments_fiscal_status_not_required.sql`
- CHECK: `NULL | registered | pending | not_required`
- Предфильтр: terminal = `{registered, not_required}`
- PR #249 merged; deploy-vps success
- Реестр: `sfrfr_ops.schema_migrations` filename applied

## Prod data (supabase2)

```text
UPDATE payments SET fiscal_status='not_required'
WHERE id='c05f1cfc-8077-410f-aff6-a9d717211b6c' AND fiscal_status IS NULL;  -- 1 row
UPDATE payments SET fiscal_status='not_required'
WHERE id='d5d29b06-2ebd-4242-bfce-1b6edf976e9f' AND fiscal_status IS NULL;  -- 1 row
```

## Timer (app-VPS `91.229.11.147`)

- `.env`: `FISCAL_RECONCILE_ENABLED=1`, `DRY_RUN=1`,
  `ALERT_SINCE=2026-10-23T17:47:35Z` (момент включения, не one-shot 17:32)
- `sfrfr-fiscal-reconcile.timer`: **enabled / active**
- Первый tick после включения: **candidates=9** (7+2 pending; 1₽ вне выборки)

## Дальше

2–3 часа dry-run логов → один CLI на NULL с чеком (проверить `registered`) →
отдельный create → `DRY_RUN=0`.
