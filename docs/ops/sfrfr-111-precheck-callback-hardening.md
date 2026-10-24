# SFRFR-111: hardening callback-контура (после ревью)

**Head:** после push на #269.  
**Unit:** 61 passed (handler routing + lifecycle + primary + staff_document_check).  
Приёмку **не** закрывать. Merge/deploy/live — нет.

## Исправления по ревью

| Разрыв | Фикс |
|---|---|
| Кнопки без `check_id` | `precheck:<sub>:<check_id>` в генераторе; коммерция только с cid |
| Handler не передавал version | `_handle_precheck_callback_event` → `requested_check_id` |
| Stale без проверки принадлежности | `_job_belongs_to_case`; иначе `precheck_forbidden_check` |
| Legacy payload без id | мутации → `stale_missing_check_id`, действие не выполняется |
| Decline всегда ok | ok только после `_mark_declined` True; иначе `precheck_decline_failed` |
| ask_staff «отложено» | при False → `precheck_ask_staff_failed`, без deferred |
| Старый offer в карточке | `live_offer_still_allowed` на order/offer_info |
| status «завершена» по умолчанию | ветки queued/running/failed/нет primary |
| Заглушки | явный текст: upload/answer/order — route_instruction / unavailable |

## Handler-тесты (из генератора)

`tests/unit/test_precheck_handler_routing.py`: generator→handler, stale order, legacy, decline→order block, paid block, decline fail, ask_staff fail, foreign check, no case, unknown, running status, repeat.
