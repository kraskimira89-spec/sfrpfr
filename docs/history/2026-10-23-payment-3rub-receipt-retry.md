# 2026-10-23 — retry фискализации 3 ₽ (без нового платежа)

**Итог: чек ❌ fail, FD нет.**

## Контекст

Приёмка 3₽: webhook→paid ✅, чек ❌ (`receipt_registration=canceled`).
Payment `326d2067-…eb6d`, shop **1421177**, charge **3.00** RUB.
Новый платёж **не** создавали.

## Шаги

| Шаг | Результат |
|-----|-----------|
| `yookassa-status` (VPS, shop 1421177) | fiscal_provider=**evotor**, send_receipt=true, alignment ok, warnings=[] |
| Evotor hint | Контур ЮKassa ок; смена ККТ по API не видна — по прошлым cancel вероятен сбой смены |
| Email (order/case) | `s***d@e***` (smoke `…@example.invalid`) |
| `yookassa-retry-receipt` | HTTP 200, receipt `ra-326d2266-…` status **pending** |
| Поллинг | target → **canceled**; `receipt_registration=canceled`; FD=null; cancel_reason API пусто |
| Предыдущие receipts | `ra-326d20f…` ×2 тоже **canceled** |

## Вердикт

**Стоп.** Повторная фискализация уже оплаченного не дала FD.
Владельцу: нужна **открытая смена Evotor** (касса онлайн), после этого — снова `yookassa-retry-receipt` для `326d2067-…eb6d`.

Трекер: SFRFR-89 (комментарий о fail retry).
