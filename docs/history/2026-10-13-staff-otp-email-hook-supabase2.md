# 2026-10-13 — staff email OTP: Send Email Hook на supabase2

## Симптом

После cutover на `https://supabase2.proverkastaza.ru` код/письмо для входа
сотрудника в `admin.proverkastaza.ru` не приходило.

## Путь письма (канон)

1. `apps/admin` → precheck `POST /api/portal/auth/staff/email-otp/request`
   (роль staff + auth user; само письмо не шлёт).
2. `supabase.auth.signInWithOtp` → GoTrue `/auth/v1/otp`.
3. GoTrue **Auth Send Email Hook** →
   `https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email`.
4. API → `send_mail` (Postbox при `YANDEX_POSTBOX_ENABLED=true`, иначе Workspace SMTP).

## Причина

На ВМ `194.67.116.168` (`/opt/sfrfr-supabase/supabase/docker`) после cutover:

- `GOTRUE_HOOK_SEND_EMAIL_*` — пусто, overlay `docker-compose.sfrfr-email.yml` отсутствовал;
- SMTP указывал на фейковый inbucket `supabase-mail:2500`;
- в логах auth: `lookup supabase-mail … server misbehaving` на `/otp` (500).

App-VPS Postbox и `SUPABASE_SEND_EMAIL_HOOK_SECRET` были заданы; хук с GoTrue
просто не вызывался.

## Исправление (инфра, без кода)

На supabase2:

1. Бэкап `.env` → `.env.bak-email-hook-*`.
2. Секрет = `SUPABASE_SEND_EMAIL_HOOK_SECRET` с App-VPS → `GOTRUE_HOOK_SEND_EMAIL_SECRETS`.
3. Overlay `docker-compose.sfrfr-email.yml` + `GOTRUE_HOOK_SEND_EMAIL_ENABLED=true`,
   URI на API hook.
4. `ADDITIONAL_REDIRECT_URLS` / `GOTRUE_URI_ALLOW_LIST` — admin + cabinet.
5. `docker compose … up -d auth`.

На App-VPS: `STAFF_LOGIN_APPROVER_MAX_CHAT_IDS=321180237` очищен (чат `chat.not.found`);
DM руководителю по `STAFF_LOGIN_APPROVER_MAX_USER_IDS=6407832` работает.

## Smoke

- OTP `info@proverkastaza.ru`: GoTrue `Hook ran successfully`; API `smtp_ok`;
  `POST …/auth-send-email` 200.
- MAX staff login `info@`: `mode=trusted_max`, статус `pending_confirm`
  (нужно нажать кнопку в Ops-боте у max_user_id `6407832`).
