# 2026-10-23 — retry фискализации 3 ₽ (без нового платежа)

**Итог: чек ✅ ok (попытка 3), FD 768.**

`payment.receipt_registration` на платеже может ещё показывать **canceled** (история ранних попыток) — ориентир: успешный receipt + FD/FN.

## Контекст

Приёмка 3₽: webhook→paid ✅; чек сначала ❌, затем ✅ после ручного retry и привязки кассы.
Payment `326d2067-…`, shop **1421177**, charge **3.00** RUB.
Новый платёж **не** создавали.

## Попытка 1 (до открытия смены)

| Шаг | Результат |
|-----|-----------|
| `yookassa-status` (VPS, shop 1421177) | fiscal_provider=**evotor**, send_receipt=true, alignment ok, warnings=[] |
| Evotor hint | Контур ЮKassa ок; смена ККТ по API не видна — по прошлым cancel вероятен сбой смены |
| Email (order/case) | smoke `…@example.invalid` |
| `yookassa-retry-receipt` | HTTP 200, receipt `ra-326d2266-…` status **pending** |
| Поллинг | target → **canceled**; `receipt_registration=canceled`; FD=null; cancel_reason API пусто |

## Попытка 2 (владелец: «смена открыта»)

| Шаг | Результат |
|-----|-----------|
| `yookassa-status` | fiscal_provider=**evotor**, SEND_RECEIPT=true, warnings=[] |
| `yookassa-retry-receipt` (1×) | HTTP 200, receipt `ra-326d24b5-…` status **pending** |
| Поллинг (~сразу) | **canceled**; `receipt_registration=canceled`; FD/FN=null; `cancellation_details`=null |
| Новый платёж | **не** создавали |

## Попытка 3 (после привязки кассы) — успех

| Поле | Значение |
|------|----------|
| Payment | `326d2067-…` (тот же; нового нет) |
| Receipt | `ra-326d35fb-…` |
| FD | **768** |
| FN | `7385440800007929` |
| Shop | **1421177** |
| `payment.receipt_registration` | может оставаться **canceled** — не путать с фактом FD |

## Вердикт приёмки webhook+чек (3₽)

| Критерий | Статус |
|----------|--------|
| Webhook → paid | ✅ (ранее) |
| Чек / FD | ✅ FD **768** (ручной retry после привязки) |
| Новый платёж | нет |

**Риск:** офлайн-точка без роутера — смена/касса могут снова не принимать чек.

Трекер: SFRFR-89.
