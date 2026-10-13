# 2026-10-13 — cutover на supabase2 (reg.ru)

Инцидент SFRFR-73: Яндекс-ВМ db-01 недоступна; рабочий стек на reg.ru.

## Сделано

- DNS `A supabase2` → `194.67.116.168` (запись `A supabase` → `51.250.69.237` не меняли).
- Caddy: `PROXY_DOMAIN` / `API_EXTERNAL_URL` / `SUPABASE_PUBLIC_URL` =
  `https://supabase2.proverkastaza.ru`; LE выпущен; `curl -I` → 401.
- UFW + `DOCKER-USER`: TCP 5433 только с App-VPS `91.229.11.147`.
- App-VPS `/opt/sfrfr/.env` (+ cabinet/admin): бэкап
  `.env.bak-supabase2-2026-10-13`; URL → supabase2; `DATABASE_URL`/`DBT_HOST` →
  `194.67.116.168`. Рестарт API/кабинетов; rebuild Next для `NEXT_PUBLIC_*`.
- Smoke: `api/health` 200; auth health 200; staff OTP request не 500.

## Осталось

- Догонка миграций на дампе (в т.ч. `document_ingest_jobs` → PGRST205 у ingest-воркера).
- Emergency leads `source=max` (2) и буфер MAX — отдельный разбор клиентов без дела.
- realtime на ВМ был unhealthy (не блокер входа).
