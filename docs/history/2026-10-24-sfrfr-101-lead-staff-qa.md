# 2026-10-24 — SFRFR-101: QA lead под staff + smoke без токена

## Сделано

- Канон QA: `docs/qa/lead-staff-e2e.md` (без обязательного amo).
- `docs/qa/lead-amocrm-e2e.md` помечен **РЕЗЕРВ**.
- Smoke (без создания лида), UTC **2026-10-24T05:09:32Z**:
  - `GET /health` → ok, env=production
  - `POST /api/public/leads` без токена → **401** (эндпоинт жив)

## Не сделано (ждёт согласования)

- Полный E2E с `PUBLIC_LEAD_TOKEN` → case в staff (тестовый lead без реальных ПДн клиента).

## Код

`public_leads._require_amocrm_lead`: при `AMOCRM_ENABLED=0` amo lead не требуется (проверено чтением).
