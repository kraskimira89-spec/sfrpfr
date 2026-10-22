# 2026-10-22 — тестовые платежи ЮKassa по 1 ₽

Владелец: тестовые оплаты по 1 руб, не по боевым 3000/5000/8000.

## Решение

- Helper `yookassa_charge_amount_rub` (`src/sfrfr/services/payment_amount.py`).
- Автоматически при секрете `test_…`; опционально `PAYMENT_TEST_AMOUNT_ENABLED=1`.
- Сумма: `PAYMENT_TEST_AMOUNT_RUB` (default 1).
- Точки: `POST .../pay`, `ensure_yookassa_pay_url` (invoice + fallback payment).
- Публичные тарифы и `orders.amount_rub` без изменений.

## Включение на VPS

В `.env` тестового контура — ключи тестового магазина (`test_…`).  
Дополнительно можно явно: `PAYMENT_TEST_AMOUNT_RUB=1`.  
Рестарт API после смены env.
