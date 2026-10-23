# 2026-10-23 — retry фискализации 3 ₽ (без нового платежа)

**Итог: чек ❌ fail, FD нет.**

## Контекст

Приёмка 3₽: webhook→paid ✅, чек ❌ (`receipt_registration=canceled`).
Payment `326d2067-…eb6d`, shop **1421177**, charge **3.00** RUB.
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

## Вердикт

**Стоп.** Два retry уже оплаченного платежа — оба **canceled**, FD нет.
Владельцу: в Evotor убедиться, что смена **реально** открыта на кассе/терминале, привязанном к магазину ЮKassa **1421177**, касса онлайн; затем снова один `yookassa-retry-receipt` для `326d2067-…eb6d`.

Трекер: SFRFR-89.
