# 2026-10-23 — SFRFR-93 commit 4 (fiscal reconcile job)

Ветка `sfrfr-93-fiscal-reconcile`, PR #247.

## Сделано

- Выборки: окно/`ALERT_SINCE` в PostgREST `or_`, `order(paid_at)`, явный select без `reconcile_post_payload`.
- `create_receipt`: `phase` = `pre_post` | `transport` | `http`; без `request_body` в ответе (PII).
- RPC: lease, TTL alive, mark post_started, claim alert — `now()` только из БД.
- Job `fiscal_reconcile_job` + CLI `fiscal-reconcile-tick` / reset-alert; `yookassa-retry-receipt` на lease.
- Systemd timer/service; runbook в `docs/yookassa-setup.md`.
- Env: `FISCAL_RECONCILE_ENABLED=0`, `DRY_RUN=1` по умолчанию.

## Не сделано здесь

- Миграция на Supabase preview / prod.
- Полный прогон тестов 1–28 на preview.
- Включение timer на VPS.
