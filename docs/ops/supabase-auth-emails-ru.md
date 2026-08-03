# Русские письма Auth (Supabase)

Письма регистрации / OTP / восстановления — шаблоны GoTrue.

## Файлы

- `supabase/templates/confirmation.html` — регистрация / подтверждение
- `supabase/templates/magic_link.html` — код входа (OTP)
- `supabase/templates/recovery.html` — восстановление пароля

Персонализация: `{{ .Data.full_name }}` (из `signInWithOtp` → `options.data.full_name`).
Код для ввода в кабинете: `{{ .Token }}`.

## Применить на Cloud

1. Токен: https://supabase.com/dashboard/account/tokens  
2. `secrets/supabase-access.env` (не коммитить):

```env
SUPABASE_ACCESS_TOKEN=sbp_...
SUPABASE_PROJECT_REF=frualvycousvvyjivybu
```

3. Запуск:

```bash
python scripts/supabase_patch_auth_emails.py
```

Либо вручную: Dashboard → Authentication → Email Templates — вставить HTML из `supabase/templates/`.

## Dashboard (ручной путь)

Проект: https://supabase.com/dashboard/project/frualvycousvvyjivybu/auth/templates
