# 2026-10-24 — SFRFR-108: reconcile vs паттерн дубля 8000

**Вердикт:** текущий fiscal reconcile **не** повторяет исторический паттерн дубля SUPPORT 8000.
**Стоп наблюдения SFRFR-93 из-за дубля:** **нет**.

## Исторический дубль (не reconcile)

| Поле | Факт |
|---|---|
| Что | два succeeded `type=payment` на один платёж |
| Причина | webhook/`ensure_payment_receipt` при `reg=pending` + авточек invoice |
| Док | `2026-10-23-battle-support-8000.md`, `receipt-dedup-ensure-gate.md` |
| Задача | SFRFR-89 |

## Текущие gates (код)

| Слой | Поведение | Где |
|---|---|---|
| Webhook | `should_auto_retry_fiscal_receipt` → только `canceled`/`cancelled` | `payments/__init__.py`, routes |
| `ensure_payment_receipt` | skip при `reg=succeeded` или `pending`; иначе `payment_receipt_retry_gate` по list | тот же модуль |
| Fiscal reconcile tick | сначала `should_auto_retry` (иначе `skip_pending`/`skip_reg`); затем `list_receipts` + `payment_receipt_retry_gate`; только потом `create_receipt` | `fiscal_reconcile_job.py` |

## Тесты (регрессия gates)

- `test_should_auto_retry_fiscal_only_after_canceled`
- `test_ensure_receipt_skips_when_succeeded_type_payment_exists`
- `test_webhook_http_pending_does_not_call_ensure_or_create_receipt`
- `test_process_skip_pending_no_create`
- `test_process_gate_before_create`

Запуск (локально): точечный pytest этих тестов.

## Ограничения

- Live-гонка «закрытая смена / долгий pending» — отдельно SFRFR-94; не закрыта этим выводом.
- Новый боевой платёж для воспроизведения — без согласования не проводить.
- Наблюдение SFRFR-93 продолжать в существующем режиме без новых изменений env этим выводом.

## Связанные задачи

SFRFR-108 (эта сверка), SFRFR-89, SFRFR-93, SFRFR-100.
