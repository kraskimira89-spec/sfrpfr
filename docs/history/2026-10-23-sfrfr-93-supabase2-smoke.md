# 2026-10-23 — SFRFR-93 smoke на supabase2 (до merge #247)

## Цель

Миграция fiscal reconcile + RPC/or/dry-run на рабочей БД supabase2
(`194.67.116.168`), пока YC недоступен.

## Бэкап

`/srv/supabase-data/restore/pre-sfrfr93-payments-20261023T171800Z.dump`  
(`pg_dump -Fc -t public.payments`)

## Миграция

- PG `server_version` = **17.6**
- Применено от **`supabase_admin`** (`postgres` → must be owner of table payments)
- `SET lock_timeout='5s'`, одна транзакция
- Реестр: `20261023180000_payments_fiscal_reconcile_attempts.sql` @ 2026-10-23 17:18:10+00
- Колонки: `last_reconcile_at`, `reconcile_*` (7 шт.)
- RPC: `try_fiscal_reconcile_lease`, `fiscal_reconcile_ttl_alive`,
  `mark_fiscal_reconcile_post_started`, `claim_fiscal_reconcile_alert`

## Smoke (без PII)

| Проверка | Результат |
|----------|-----------|
| lease 1 / 2 | 1 row / 0 rows |
| TTL NULL / −1h / −24h | f / t / f |
| claim 1 / 2 | 1 / 0; поля restore |
| PostgREST `or` count | **2** |
| `registered` в выборке окна | **0** |
| dry-run tick | 11× `dry_run`; `lease_changed=11`; `non_lease_field_changes=0` |
| timer | unit absent / inactive |

## App-VPS

Код ветки временно checkout path-only для tick, затем возврат к HEAD deploy.
Timer не включали.

## Дальше

Merge #247 (auto-merge вручную после ревью вывода). Timer prod — только с
`ENABLED=1` + `ALERT_SINCE` после логов «создал бы».
