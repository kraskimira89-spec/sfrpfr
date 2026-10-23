# 2026-10-23 — приёмка DIAG 3 ₽ (после отмены 3000, shop 1421177)

**Вердикт: ✅ принято** (с оговорками) — webhook→paid ок ранее; чек ✅ FD **768** после ручного retry и привязки кассы. Reconcile **не** делали. Поле `payment.receipt_registration` может ещё быть **canceled**.

## Факты

| Поле | Значение (masked) |
|------|-------------------|
| Дело | ПС-275527 / `4ef915ef-…3447` (`is_test`) |
| Старый order | `f4464298-…b5b6` → **cancelled** (`owner_reissue_test_3rub`) |
| Order | `b28cc23c-…b873`, amount_rub **3000.00** (тариф), status **paid** |
| Charge YK | **3.00** RUB, `paid=true`, `succeeded` |
| Payment | `326d2067-…eb6d` = `provider_payment_id` (ровно 1 строка) |
| Invoice | `in-326d1fee-…6ff1` |
| Shop / recipient | **1421177** |
| Captured | `2026-10-23T07:30:58Z` |
| Webhook | Apache `POST …/yookassa/webhook` **200** (`10:30:58 +0300`, AHC) — совпадает с `payments.paid_at` |
| b2c | **diagnostic_paid** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | **0** (process `sfrfr-api`); `RUB=3` в env, флаг выкл. |
| Чек | ранние `ra-326d20f3-…` / `ra-326d20f2-…` **canceled**; успешный `ra-326d35fb-…`, FD **768**, FN `7385440800007929` |
| MAX / кабинет клиента | `max_user_id=null`, `user_id=null` — UI канала N/A; staff login не открыт |

## Критерии Стратега (сумма=3₽)

| Критерий | Статус |
|----------|--------|
| YK succeeded, amount 3.00, shop 1421177 | ✅ |
| Access log: POST webhook 200 около оплаты | ✅ |
| БД: order paid + `provider_payment_id` совпадает, без reconcile | ✅ |
| Один платёж | ✅ |
| Чек / FD | ✅ FD **768** (ручной retry после привязки; `receipt_registration` на payment может ещё canceled) |
| MAX/кабинет: один платёж | ➖ N/A (smoke без привязки) / БД: один |
| `PAYMENT_TEST_AMOUNT_ENABLED=0` | ✅ |

## Итог

**Принято по 3₽ пути** (с оговоркой): webhook ок ранее; чек ok после ручного retry; риск офлайн точки без роутера. Новый платёж не создавали.

## Retry фискализации (тот же payment)

См. `2026-10-23-payment-3rub-receipt-retry.md`: попытки 1–2 canceled; попытка 3 → `ra-326d35fb-…`, FD **768** (SFRFR-89).
