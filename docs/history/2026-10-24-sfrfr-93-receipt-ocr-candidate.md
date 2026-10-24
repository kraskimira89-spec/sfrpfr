# 2026-10-24 — SFRFR-93: кандидат `receipt:…` (диагностика)

**Окно наблюдения не перезапускалось.** Строку платежа **не** правили вручную
(`fiscal_status` / attempts / alert claim не трогали).

## Факт из journal / БД

| Поле | Значение |
|---|---|
| payment.id | `89be641d-a187-4c0d-b61e-d8939889ccdf` |
| provider | **`receipt_ocr`** |
| provider_payment_id | **`receipt:b18c6771-bbb8-4ce9-9045-62f094f4590a`** |
| order_id | `b18c6771-bbb8-4ce9-9045-62f094f4590a` (= uuid после `receipt:`) |
| status | succeeded |
| fiscal_status | NULL |
| paid_at | 2026-10-24T11:56:51Z |
| Тики | 15:01 и 15:11 MSK → `candidates=1`, `action=error_before_post` |
| error | `Incorrect payment_id. Payment doesn't exist or access denied…` |
| reconcile_attempts | **0** |
| reconcile_pre_error_streak | **2** (после двух тиков) |
| reconcile_last_outcome | `error_before_post` |
| reconcile_post_at | NULL |
| reconcile_alerted_at | NULL |
| Аналоги `receipt:%` | **1** строка (эта) |

## Ответы на контрольные вопросы

1. **Шаг ошибки:** `fetch_payment(yk_id)` — до list/gate/create.  
   Код: `fiscal_reconcile_job` сразу после lease, ветка `not fetched.ok` → `error_before_post` + streak+1.
2. **Create:** **не вызывался** (`reconcile_post_at` NULL, attempts=0, нет mark_post_started). Название `error_before_post` здесь = fail **до** POST чека.
3. **Attempts / streak:** attempts остаются 0; streak растёт каждый тик (2 при двух наблюдениях). Стоп-алерт streak≥12 — **не** достигнут.
4. **Откуда `receipt:`:** канон `payment_receipt.confirm_order_from_receipt`:  
   `provider_payment_id = f"receipt:{document_id or order_id}"`, `provider="receipt_ocr"`.  
   Назначение поля — синтетический ключ оплаты по загруженному чеку OCR, **не** ID платежа ЮKassa.
5. **Исключения:** в выборке reconcile **не** было фильтра по provider / префиксу → **новый дефект данных/выборки** (не известный waiver 1₽). Риск неверного create при текущем коде: **низкий** (fetch падает раньше), но streak шумит и упрётся в sticky alert.

## Меры

- Не обрезать `receipt:` и не подставлять другой ID.
- Код: исключить `receipt_ocr` / `receipt:` из `filter_reconcile_candidates` (+ stale) — PR без auto-merge; строку в БД не трогать.
- Отсчёт окна SFRFR-93 **без** перезапуска.
