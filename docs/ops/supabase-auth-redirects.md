# Supabase Auth: redirect URLs для кабинета

Для восстановления пароля клиент вызывает
`resetPasswordForEmail(..., { redirectTo: 'https://cabinet.proverkastaza.ru/?mode=recover' })`.

## Прод (self-host Yandex Cloud) — актуальный контур

Хост Auth: `https://supabase.proverkastaza.ru`  
Конфиг: `/opt/sfrfr-supabase/supabase/docker/.env` на ВМ staging/prod Supabase.

- **SITE_URL:** `https://cabinet.proverkastaza.ru`
- **ADDITIONAL_REDIRECT_URLS** (минимум):
  - `https://cabinet.proverkastaza.ru/**`
  - `https://cabinet.proverkastaza.ru/?mode=recover`
  - `https://admin.proverkastaza.ru/**`

После правки: `docker compose up -d auth --force-recreate`  
Скрипт: `scripts/yc_set_auth_redirects.sh`

Без allow-list письмо recovery откроет ошибку redirect / не завершит смену пароля.

## Legacy (Supabase Cloud) — до drain

Проект: `frualvycousvvyjivybu`  
Dashboard → Authentication → URL Configuration — только для rollback, пока Cloud жив.

Сводка cutover: [cutover-manual-checklist.md](./cutover-manual-checklist.md).
