# 2026-10-24 — SFRFR-93: кандидат `receipt:…` (диагностика)

**Окно наблюдения не перезапускалось.** Строку платежа **не** правили вручную
(`fiscal_status` / attempts / alert claim не трогали).

Полные UUID платежей/заказов в этот файл **не** кладём (правило волны).

## Факт из journal / БД (обезличено)

| Поле | Значение |
|---|---|
| payment.id | `89be641d…` (префикс) |
| provider | **`receipt_ocr`** |
| provider_payment_id | **`receipt:{order_uuid}`** (синтетика OCR) |
| status | succeeded |
| fiscal_status | NULL |
| paid_at | 2026-10-24 ~11:56Z |
| Тики | ~15:01 и ~15:11 MSK → `candidates=1`, `action=error_before_post` |
| error | Incorrect payment_id / access denied (ЮKassa) |
| reconcile_attempts | **0** |
| reconcile_pre_error_streak | **2** (два тика) |
| reconcile_last_outcome | `error_before_post` |
| reconcile_post_at | NULL |
| reconcile_alerted_at | NULL |
| Аналоги `receipt:%` | **1** строка (эта) |

## Ответы на контрольные вопросы

1. **Шаг ошибки:** `fetch_payment` — до list/gate/create.  
2. **Create:** **не вызывался** (`post_at` NULL, attempts=0).  
3. **Attempts / streak:** attempts=0; streak рос на тик (2). Стоп≥12 не достигнут.  
4. **Откуда `receipt:`:** `payment_receipt.confirm_order_from_receipt` —  
   `provider=receipt_ocr`, `provider_payment_id=receipt:{doc|order}`; не ID ЮKassa.  
5. **Исключения:** фильтра не было → дефект выборки. Риск create низкий (fail на fetch).

## Контракт фильтра (срочный патч)

`provider_payment_is_yookassa_reconcile_target`: исключаем известные OCR
(`receipt_ocr` / `receipt:`). Прочие provider **не** whitelist'им в этом PR —
отдельный follow-up.

## Меры

- Строку БД не трогать; префикс не обрезать «в данных».
- Код: исключить OCR из reconcile + stale (#260); окно без перезапуска.
- После deploy: тики без OCR-кандидата; streak OCR не растёт; разделить периоды до/после в 24ч-отчёте.
