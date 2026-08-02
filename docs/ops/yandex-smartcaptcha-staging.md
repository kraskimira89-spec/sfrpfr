# Yandex SmartCaptcha — пилот staging (ТЗ-15)

Прод на MVP остаётся на **Google reCAPTCHA Enterprise**.  
SmartCaptcha подключаем параллельно для staging / последующего cutover.

## 1. Создать капчу в Yandex Cloud

1. Консоль → каталог `default` → **SmartCaptcha**.
2. Создать капчу для домена staging-формы (например `proverkastaza.ru` / staging host).
3. Скопировать:
   - **Клиентский ключ** → `SMARTCAPTCHA_CLIENT_KEY`
   - **Серверный ключ** → `SMARTCAPTCHA_SERVER_KEY` (только сервер, не в WP/HTML публично как secret)

## 2. Env (API)

```env
CAPTCHA_PROVIDER=yandex
# или auto — если задан SMARTCAPTCHA_SERVER_KEY, он приоритетнее Google
SMARTCAPTCHA_SERVER_KEY=…
SMARTCAPTCHA_CLIENT_KEY=…
```

Проверка токена: `POST https://smartcaptcha.cloud.yandex.ru/validate`  
(модуль `src/sfrfr/integrations/smartcaptcha/`).

API лида принимает:

- `smartcaptcha_token` **или**
- `recaptcha_token` (тот же слот, если провайдер yandex/auto→smart)

## 3. Витрина (WP / staging-форма)

Подключить виджет SmartCaptcha по [quickstart](https://yandex.cloud/ru/docs/smartcaptcha/quickstart) с `SMARTCAPTCHA_CLIENT_KEY`.  
В webhook/JSON на `/api/public/leads` передать токен как `smartcaptcha_token`.

**Не** выключать Google на проде, пока staging-пилот не зелёный и cutover captcha не согласован.

## 4. Критерий пилота

- [ ] Ключи созданы в YC (РФ).
- [ ] API с `CAPTCHA_PROVIDER=yandex` отклоняет пустой токен вне debug.
- [ ] Успешный лид со staging-формы с валидным SmartCaptcha-токеном.
- [ ] Prod по-прежнему на Google, пока не начата фаза 3 ТЗ-15.
