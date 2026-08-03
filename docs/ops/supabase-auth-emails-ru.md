# Русские письма Auth (Supabase) + отправитель РФ

По умолчанию Cloud шлёт с `noreply@mail.app.supabase.io` (GoTrue).  
Для продакшена используем **Auth Send Email Hook** → API SFRFR → **Яндекс SMTP** (`proverkastaza@yandex.ru`).

## Отправитель

- **From name:** `Проверка стажа. Личный кабинет`
- **From address:** `proverkastaza@yandex.ru` (Яндекс Workspace / OAuth XOAUTH2)
- **Endpoint:** `POST https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email`

## Переменные

```env
# на VPS /opt/sfrfr/.env и локально (не коммитить)
SUPABASE_SEND_EMAIL_HOOK_SECRET=v1,whsec_...
YANDEX_MAIL_ENABLED=true
YANDEX_OAUTH_ACCESS_TOKEN=...
YANDEX_WORKSPACE_EMAIL=proverkastaza@yandex.ru
```

## Включить хук (Management API)

1. PAT: https://supabase.com/dashboard/account/tokens → `secrets/supabase-access.env`
2. Сгенерировать секрет и прописать в `.env` / VPS, затем:

```bash
python scripts/supabase_enable_auth_send_email_hook.py
# или с уже известным секретом:
python scripts/supabase_enable_auth_send_email_hook.py --secret "v1,whsec_..."
```

3. Перезапустить API (`systemctl restart sfrfr-api`), дождаться деплоя кода с роутом.

Выключить (вернуть mailer Supabase):

```bash
python scripts/supabase_enable_auth_send_email_hook.py --disable
```

## HTML-шаблоны (fallback / локальный GoTrue)

Если хук выключен, Cloud использует шаблоны GoTrue:

- `supabase/templates/confirmation.html`
- `supabase/templates/magic_link.html`
- `supabase/templates/recovery.html`

Применить темы/тексты (не меняют From-домен):

```bash
python scripts/supabase_patch_auth_emails.py
```

Dashboard: https://supabase.com/dashboard/project/frualvycousvvyjivybu/auth/templates

## Проверка

1. Запросить код в кабинете.
2. В письме: отправитель «Проверка стажа. Личный кабинет», адрес `proverkastaza@yandex.ru` (не `mail.app.supabase.io`).
