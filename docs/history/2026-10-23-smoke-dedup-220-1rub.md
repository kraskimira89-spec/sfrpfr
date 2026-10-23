# 2026-10-23 — smoke дедуп чеков #220 (1 ₽)

Владелец: «да, платим 1».

## Создание

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | **0** (не включали) |
| Amount | **1.00** RUB |
| Payment id (**KEEP / оплатить**) | `326d7173-000f-5000-b000-11426487b1f7` |
| Status (create) | `pending` |
| Confirmation | `https://yoomoney.ru/checkout/payments/v2/contract?orderId=326d7173-000f-5000-b000-11426487b1f7` |
| return_url | `https://proverkastaza.ru/` |
| receipt | email `smoke@proverkastaza.ru` |
| metadata | `channel=smoke_dedup_220` |
| PR #222 | MERGED |

## Дубль (не оплачивать)

Параллельно создан второй pending:

| Поле | Значение |
|------|----------|
| Payment id (**IGNORE**) | `326d715b-000f-5001-9000-104a03862dfc` |
| created_at | `2026-10-23T13:14:04Z` (старше KEEP) |
| Status | `pending`, `paid=false` |
| `POST …/cancel` | **400** — для unpaid redirect ЮKassa не отменяет; оставить неоплаченным (истечёт) |

Стратег: **один** платёж. Владельцу отдана только ссылка KEEP.

## Критерий PASS

`GET /v3/receipts?payment_id=` → ровно **1** `type=payment` (succeeded\|pending). Два = FAIL.

## После оплаты

Владелец: «оплатил».

| Поле | Значение |
|------|----------|
| Pay status | **succeeded** / paid |
| `receipt_registration` | **succeeded** |
| Receipts raw | **1** |
| `type=payment` (succeeded\|pending) | **1** |
| Receipt id | `ra-326d7360-0002-0050-73be-48e949d93427` |
| FD | **774** |
| Вердикт | **PASS** → `BLOCKER_CLEARED` |

Дубль `326d715b-…` не смотрели / не оплачивали.
