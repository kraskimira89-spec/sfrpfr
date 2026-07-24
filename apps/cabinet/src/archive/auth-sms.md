# Архив: вход по SMS (не публиковать)

Флаг в кабинете: `AUTH_SMS_PUBLISHED = false` в `client-cabinet.tsx`.

Чтобы снова включить:

1. Поставить `AUTH_SMS_PUBLISHED = true`.
2. В Supabase Auth включить Phone provider / SMS.
3. Проверить вкладку «Телефон» на экране входа.

## Бывший UI

- Вкладка «Телефон» рядом с MAX / Email.
- `supabase.auth.signInWithOtp({ phone })` → `verifyOtp({ phone, type: "sms" })`.

## Статус

Отключено 2026-07-24: SMS-провайдер не подключён, для аудитории основной вход — MAX и email.
