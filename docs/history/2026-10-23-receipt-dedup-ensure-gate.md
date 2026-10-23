# 2026-10-23 — дубль чеков FD 770/771: причина и gate ensure

**Вердикт для Стратега:** дубль **наш код** (автоповтор PR #195), не «магия Evotor» и не пара payment+refund.

## Пример

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| Payment | `326d4ecc…03b4`, **5.00** RUB, succeeded |
| Чеки | FD **770** + **771**, оба `type=payment` / `succeeded` |
| Параллель | 8₽ `326d4ef1…7321` → FD **772** + **773** (тот же паттерн) |

## Классификация кандидатов

| Кандидат | Вердикт |
|----------|---------|
| Повтор ЮKassa сама | нет отдельного сигнала; два разных receipt id |
| Evotor ручной пробив | маловероятно: один чек со `settlements=cashless` (наш `POST /v3/receipts`), второй без settlements (чек из `create_payment`) |
| Автоповтор PR #195 | **да** — webhook/`ensure_payment_receipt` смотрел только `payment.receipt_registration`, а не список receipts |
| Ручной `yookassa-retry-receipt` | тот же код `ensure_payment_receipt`; усиливает риск при уже живом чеке |

## Баг

`ensure_payment_receipt` делал `POST /receipts`, если `receipt_registration ≠ succeeded`.
Поле registration может отставать / оставаться `canceled`, пока чек из `create_payment` уже `succeeded` (или оба уходят в ККТ параллельно) → второй succeeded `type=payment`.

## Фикс

- `GET /v3/receipts?payment_id=`
- Повтор **только** если нет `type=payment` со статусом `succeeded` (и не `pending` в полёте)
- TDD: `test_ensure_receipt_skips_when_succeeded_type_payment_exists`

## Боевой прогон 3/5/8k

Дубль = **жёсткий блокер** до фикса в проде: `docs/ops/plan-battle-payment-run-3000-5000-8000.md` → статус `FIX_IN_FLIGHT` / после деплоя `BLOCKER_CLEARED`.
Не писать «тарифы приняты».

Трекер: SFRFR-89.
