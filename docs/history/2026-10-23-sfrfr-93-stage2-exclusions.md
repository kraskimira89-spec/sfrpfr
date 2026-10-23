# Этап 2: исключения из окна

## fiscal_status (supabase2)

- CHECK `payments_fiscal_status_chk`: `NULL | registered | pending | not_required`
- DISTINCT до правок этапа: `NULL`, `pending`, `registered` (+ уже `not_required` у 1₽)

## 1 ₽ smoke (ранее, SFRFR-98)

| id8 | yk | было | стало |
|-----|-----|------|-------|
| c05f1cfc | 326d0ff7-000f | NULL | not_required |
| d5d29b06 | 326d17bf-000f | NULL | not_required |

## pending чужой shop (SFRFR-99)

`fetch_payment` → Incorrect payment_id / access denied → не наш контур.

| id8 | yk | было | стало |
|-----|-----|------|-------|
| d74c6a42 | 326cf802-000f | pending | not_required |
| b8bd28a7 | 326cf928-000f | pending | not_required |

Правки: по одной строке `WHERE id=… AND fiscal_status=…`, роль `supabase_admin`.

## Проверка

`fiscal-reconcile-tick` (ENABLED=1 DRY_RUN=1): **candidates=7** — только NULL с succeeded-чеком; 1₽ и pending вне выборки.
