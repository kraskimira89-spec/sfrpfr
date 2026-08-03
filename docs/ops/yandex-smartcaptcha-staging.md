# Yandex SmartCaptcha — прод (ТЗ-15)

Целевой провайдер капчи на витрине: **Yandex SmartCaptcha**.  
Google reCAPTCHA Enterprise остаётся legacy (`CAPTCHA_PROVIDER=google`).

## 1. Создать капчу в Yandex Cloud

1. Консоль → каталог → **SmartCaptcha**.
2. Создать капчу для доменов:
   - `proverkastaza.ru`
   - `www.proverkastaza.ru`
3. Скопировать:
   - **Клиентский ключ** (`ysc1_…`) → `SMARTCAPTCHA_CLIENT_KEY`
   - **Серверный ключ** (`ysc2_…`) → `SMARTCAPTCHA_SERVER_KEY` (только сервер)

## 2. Env (API + WP)

Локально `.env` и на VPS `/opt/sfrfr/.env`:

```env
CAPTCHA_PROVIDER=yandex
SMARTCAPTCHA_SERVER_KEY=ysc2_…
SMARTCAPTCHA_CLIENT_KEY=ysc1_…
```

Проверка токена: `POST https://smartcaptcha.cloud.yandex.ru/validate`  
(модуль `src/sfrfr/integrations/smartcaptcha/`).

API лида принимает `smartcaptcha_token` (или устаревший слот `recaptcha_token`).

## 3. Витрина (WP)

MU-плагин `sfrfr-recaptcha-lead.php` + JS `scripts/assets/sfrfr-recaptcha-lead.js`:

- виджет «Я не робот» перед кнопкой отправки;
- клиентский ключ из `/opt/sfrfr/.env` → `mu-plugins/sfrfr-lead.config.php`
  (www-data не читает `.env` напрямую; server key в конфиг WP не кладётся);
- токен уходит в FastAPI как `smartcaptcha_token`.

Выкладка:

```bash
bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
systemctl restart sfrfr-api
```

## 4. Критерий готовности

- [x] Ключи созданы в YC (РФ) — капча `proverkastaza`.
- [x] `CAPTCHA_PROVIDER=yandex` на VPS `/opt/sfrfr/.env`.
- [ ] На https://proverkastaza.ru/#zayavka виден виджет SmartCaptcha (после `wp_apply_landing_vps.sh`).
- [ ] Успешный лид с отмеченной капчей.
- [ ] Без капчи API отвечает `400 captcha_token required` / `smartcaptcha_failed`.

## 5. Откат на Google

```env
CAPTCHA_PROVIDER=google
```

и временно вернуть старый JS Enterprise (git history) — только как аварийный fallback.
