# 2026-10-23 — сверка оплат после «оплата прошла»

## Магазин

- VPS: `YOOKASSA_SHOP_ID=1421177`, `PAYMENT_TEST_AMOUNT_ENABLED=0`
- Локальный `.env` ещё может указывать 1417002 (не путать при проверках)

## Кандидат 1 — smoke brand 1421177

| Поле | Значение |
|------|----------|
| payment_id | `326d0986-000f-5000-b000-14861afd73b1` |
| shop | **1421177** |
| status | **succeeded**, paid=true |
| amount | **1.00** RUB |
| в БД SFRFR | нет (metadata без order/case — ожидаемо) |
| webhook → API | **не дошёл** (в access-логе api сегодня нет POST `/payments/yookassa`) |

Чек: `receipt_registration=canceled` (smoke без customer email — ок для бренда).

## Кандидат 2 — SUPPORT «8k» ПС-775093

| Поле | Значение |
|------|----------|
| case | `326351dd-…bd3b5` → **ПС-775093** |
| order | `2ba6d703-…` ACCOMP / Шаг 3, amount_rub=8000 |
| pay_url | `…/i/atrlNQInXUUh/a` (создан **до** cutover) |
| payment_id | `326cf928-000f-5000-b000-1d9b8c069116` |
| shop | **1417002** (старый) |
| YooKassa | **succeeded**, paid=true |
| charged | **1.00** RUB (`channel=smoke_support_8k`) — не 8000 |
| до reconcile | order `awaiting_payment`, строки payment не было |
| после reconcile | order **paid**, payment **succeeded**, `newly_paid=true` |
| b2c_status | `service_paid` (уже был после DOCS 5k) |

На магазине **1421177** за 3 дня единственный succeeded — smoke brand 1₽. Платежа 8000.00 нет.

## Webhook ЛК

API webhooks ЮKassa через Basic Auth недоступны. В ЛК магазина **1421177** → Интеграция → HTTP-уведомления:

```text
https://api.proverkastaza.ru/api/integrations/payments/yookassa/webhook
```

События: `payment.succeeded` (и при необходимости `payment.waiting_for_capture` / `payment.canceled`).

Без этого reconcile вручную / скриптом останется нормой после cutover.

## Итог

1. Brand smoke на 1421177 — оплачен, бренд ок.
2. SUPPORT этап в БД закрыт по оплате (smoke 1₽ на старом магазине + ручной reconcile).
3. Реальных **8000 ₽** на новом магазине не было.
4. Webhook на 1421177 — прописать у владельца.
