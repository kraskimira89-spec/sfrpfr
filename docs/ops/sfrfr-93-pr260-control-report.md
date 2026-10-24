# SFRFR-93 / PR #260 — контрольный отчёт (к ручному merge)

```text
PR / точный head: https://github.com/kraskimira89-spec/sfrpfr/pull/260
  (обновить SHA после push этого follow-up; auto-merge OFF)

Причина:
  confirm_order_from_receipt пишет provider=receipt_ocr и
  provider_payment_id=receipt:{doc|order}. Выборка reconcile не исключала
  OCR → fetch_payment → error_before_post, streak++. Create не вызывался.

Где выполняется фильтр:
  provider_payment_passes_ocr_exclusions в
  filter_reconcile_candidates и filter_stale_alert_candidates;
  list_succeeded_payments_for_reconcile /
  list_payments_for_stale_fiscal_alert — до lease/fetch/alert.

Какие поля приходят из выборки:
  RECONCILE_PAYMENT_COLUMNS (в т.ч. provider, provider_payment_id).

Тесты reconcile:
  pytest tests/unit/test_fiscal_reconcile_queries.py
  (OCR exclude + repo list + mixed YK)

Тесты stale:
  тот же файл + filter_stale; tick hybrid stale_alerts без OCR claim

Проверка отсутствия внешних вызовов:
  test_tick_ocr_row_never_reaches_lease_fetch_create_or_alert
  — fetch только yookassa id; create/list_receipts/OCR lease/update/claim нет

Регрессия:
  pytest tests/unit/test_fiscal_reconcile_{queries,job,canon}.py
        tests/unit/test_yookassa.py
  → 104 passed (локально, SHA follow-up)

CI:
  дождаться зелёных api/cabinet/admin на точном head после push

Оставшиеся риски:
  - PostgREST limit до Python-фильтра (crowding OCR↔YK)
  - True фильтра ≠ proof provider=yookassa (whitelist отдельно)
  - live DB re-check OCR-count: MCP unreachable на срезе
  - streak OCR не сбрасывали (до 12 — стоп-порог)
  - боевой create ЮKassa этим патчем не доказан

Запрашиваемое действие: ручной merge / deploy
  (после зелёного CI на этом head; постфикс — этап Д ТЗ)
```

## После согласованной выкладки (этап Д — чеклист)

1. Merge-коммит, deployed SHA, время UTC  
2. Timer/service без смены настроек  
3. ≥3 штатных тика подряд  
4. OCR не в candidates; streak OCR не растёт; attempts/POST без изменений; нет stale-alert на OCR; YK-кандидаты не потеряны (или явно: «новый боевой create не проверен»)  

## Итог окна `2026-10-24T21:01:27Z`

Разделить: до дефекта | дефект (error_before_post, create=0) | после патча (версия + число тиков).  
Не заявлять «24ч стабильности исправленной версии», если патч работал меньше.
