# 2026-10-24 — возврат повторного SUPPORT 8000: insufficient funds

**Вердикт: ❌ деньги не возвращены** (API `403`)

Владелец: «верни 8000». Цель — повторный SUPPORT PASS (`326d8f33-…`), не первый FAIL (тот уже refunded 8000).

## Попытка

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| Payment | `326d8f33-000f-5001-9000-14edf85c8cb0` |
| Amount | **8000.00** |
| До | status `succeeded`, `refunded_amount=0.00`, `receipt_registration=succeeded` |
| HTTP | **403** |
| Error | `Insufficient funds to make a refund. Contact support to find out the reason.` |
| refund_id в теле ошибки | `01a16c32-bac2-71b7-b222-9b7c7a6719d2` (без status succeeded) |
| Чеки после | 1× `type=payment` succeeded; **0×** `type=refund` |
| После сверки | `refunded_amount` по-прежнему **0.00** |

## Не трогали

- Первый SUPPORT `326d821f-…` (уже `refunded_amount=8000.00`)
- Smoke 1₽
- Новый платёж / новый чек прихода
- `PAYMENT_TEST_AMOUNT_ENABLED` (остался `false`)

## Что нужно владельцу

1. Пополнить баланс ЮKassa shop **1421177** (или выяснить у поддержки ЮKassa, почему нет средств на refund — часто после выплаты на р/с).
2. Повторить команду «верни 8000» после пополнения — повторный `POST /v3/refunds` на тот же payment.

Скрипт (вне git-критерия, `tmp/`): `tmp/_battle_refund_8000_retry.py` на VPS `/opt/sfrfr/tmp/`.
