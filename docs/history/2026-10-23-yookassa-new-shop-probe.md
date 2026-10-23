# 2026-10-23 — ЮKassa: новый магазин (probe, без cutover)

## Контекст

Техподдержка ЮKassa: магазин **1417002** нельзя переименовать на «Проверка стажа» / `proverkastaza.ru` — нужен новый магазин и API-ключ. Владелец положил ключ в `secrets/secret_key.txt` (не в git).

## Что в файле ключа

| Поле | Значение (безопасно) |
|------|----------------------|
| Shop ID | **1421177** (новый, ≠ 1417002) |
| Secret | `live_…` (prefix `live_`, len 48) |
| Рядом | `secrets/secret_key_yumanny.txt` — старый магазин **1417002** |

Отдельного `yookassa.env` в `secrets/` нет.

## Сравнение с VPS `/opt/sfrfr/.env` (только маски)

| | VPS сейчас | Файл владельца |
|--|------------|----------------|
| `YOOKASSA_SHOP_ID` | **1417002** | **1421177** |
| Secret | `live_…` (другой last4) | `live_…` (другой last4) |
| `YOOKASSA_RETURN_URL` | `https://proverkastaza.ru/` | — |
| `YOOKASSA_SEND_RECEIPT` | `true` | — |

Локальный `.env` ещё на **1417002**; `RETURN_URL` локально был `cabinet.proverkastaza.ru` (на VPS уже канон сайта).

**Вывод:** ключ в файле — **другой магазин**, не тот же, что на проде. Cutover на VPS **не делался**.

## API probe (новый магазин 1421177)

### GET `/v3/me`

- `account_id` = `1421177`
- `status` = `enabled`
- `test` = `false` (**live**)
- `fiscalization_enabled` = `true`, provider = `evotor`
- Название / сайт магазина в `/me` **не приходят** (нет полей name/website) → бренд «taxi» vs «Проверка стажа» через API **не виден**

### POST `/v3/payments` 1.00 RUB

- Без `receipt` → `400 Receipt is missing or illegal` (ожидаемо при фискализации)
- С `receipt` (email probe) + `return_url=https://proverkastaza.ru/` → **ok**, `pending`, `paid=false`, `test=false`
- `recipient.account_id` = `1421177`
- `confirmation_url` host = `yoomoney.ru` (checkout)
- `return_url` в ответе confirmation **не эхом** (только в запросе) — канон для кода: `YOOKASSA_RETURN_URL=https://proverkastaza.ru/`
- `POST …/cancel` для `pending` redirect → 400 (ЮKassa не отменяет неоплаченный redirect так); платёж оставлен **неоплаченным** (истечёт)

Строк taxi / yumanny / proverkastaza в JSON `/me` и payment **нет**.

## План cutover VPS (только после явного «да»)

1. Бэкап `/opt/sfrfr/.env` → `.env.bak-yookassa-before-1421177-*`
2. Записать `YOOKASSA_SHOP_ID=1421177` + новый `YOOKASSA_SECRET_KEY` из `secrets/secret_key.txt`
3. Оставить `YOOKASSA_RETURN_URL=https://proverkastaza.ru/`, `YOOKASSA_SEND_RECEIPT=true`
4. В ЛК нового магазина: HTTP-уведомления →
   `https://api.proverkastaza.ru/api/integrations/payments/yookassa/webhook`
5. В ЛК: название «Проверка стажа», сайт `https://proverkastaza.ru`
6. `systemctl restart sfrfr-api` → `python -m sfrfr yookassa-status`
7. Не включать `PAYMENT_TEST_AMOUNT_ENABLED` на live без нужды

**Статус:** готов к cutover — **нужно «да» владельца** на запись ключа на VPS.

## Не делали

- Правки прод `.env`
- Коммит `secrets/`
- Оплату тестового платежа владельцем
