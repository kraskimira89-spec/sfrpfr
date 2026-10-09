# Русские письма Auth (Supabase self-host) + отправитель РФ

Канон БД: [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md).

На self-host письма Auth идут через **Auth Send Email Hook** → API SFRFR → почта РФ
(Яндекс SMTP / Yandex Cloud Postbox), а не через иностранный mailer.

## Отправитель

- **From name:** `Проверка стажа. Личный кабинет`
- **From address:** `proverkastaza@yandex.ru` (Яндекс Workspace / OAuth XOAUTH2) или Postbox
- **Endpoint:** `POST https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email`

## Переменные

```env
# на VPS /opt/sfrfr/.env и локально (не коммитить)
SUPABASE_SEND_EMAIL_HOOK_SECRET=v1,whsec_...
YANDEX_MAIL_ENABLED=true
YANDEX_OAUTH_ACCESS_TOKEN=...
YANDEX_WORKSPACE_EMAIL=proverkastaza@yandex.ru
```

## Включить хук на self-host

В Compose / `.env` стека Auth на ВМ `sfrfr-supabase-db-01` задать Send Email Hook URL и секрет
на `https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email`, затем
перезапустить Auth и API (`systemctl restart sfrfr-api`).

Redirect URLs: [supabase-auth-redirects.md](./supabase-auth-redirects.md).
