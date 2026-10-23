# 2026-10-23 — ЮKassa cutover VPS → магазин 1421177

## Решение владельца

Явное «подтверждаю изменение магазина ДА» — запись нового live-ключа на прод.

## Источник (локально, не в git)

- `secrets/secret_key.txt` → Shop ID **1421177**, secret `live_…` (len 48)
- Сверка с probe: `docs/history/2026-10-23-yookassa-new-shop-probe.md`

## VPS `/opt/sfrfr`

| Шаг | Результат |
|-----|-----------|
| Backup | `.env.bak-yookassa-cutover-20261023` |
| `YOOKASSA_SHOP_ID` | **1421177** (было 1417002) |
| `YOOKASSA_SECRET_KEY` | live, len 48 (значение не в истории) |
| `YOOKASSA_RETURN_URL` | `https://proverkastaza.ru/` |
| `YOOKASSA_SEND_RECEIPT` | `true` (без изменений) |
| `PAYMENT_TEST_AMOUNT_ENABLED` | `0` |
| Restart | `sfrfr-api` → active |

Секреты во временных `/tmp` на VPS удалены после записи.

## Проверки

### `yookassa-status`

- `account_id` = **1421177**
- `status` = enabled, `test` = false
- fiscalization: evotor, alignment ok

### Smoke create payment 1.00 RUB (+ receipt)

- `payment_id` = `326d0986-000f-5000-b000-14861afd73b1`
- `recipient.account_id` = **1421177**
- `status` = pending, `paid` = false, `test` = false
- confirmation host = `yoomoney.ru`
- return_url в запросе = `https://proverkastaza.ru/`
- Оплата **не** производилась (можно оставить expire / проверить бренд на форме)

Checkout (для проверки бренда владельцем):

`https://yoomoney.ru/checkout/payments/v2/contract?orderId=326d0986-000f-5000-b000-14861afd73b1`

## Webhook (ручной шаг в ЛК)

API webhooks ЮKassa требует OAuth; с Basic Auth shop key **нельзя** подписаться с VPS.

В ЛК магазина **1421177** → Интеграция → HTTP-уведомления:

```text
https://api.proverkastaza.ru/api/integrations/payments/yookassa/webhook
```

Также в карточке магазина: название «Проверка стажа», сайт `https://proverkastaza.ru`.

## Не делали

- Коммит `secrets/` / `.env`
- Оплату smoke-платежа
- Автонастройку webhook через API
