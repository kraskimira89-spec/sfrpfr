# SFRFR-111 cycle 5 — order → DIAG + E2E артефакты

**Дата:** 2026-10-24  
**PR:** #269  
**Merge / deploy / live MAX / prod-миграции / реальные платежи:** нет  
**SFRFR-111:** не закрывать

## 1. `precheck:order` → существующий маршрут

| Пункт контракта | Реализация |
|---|---|
| user / case / check_id | прежние gates + belongs-to-case |
| актуальность результата | stale / live_offer_still_allowed |
| основание рекомендации | offer_paid_analysis + gates заказов/отказа |
| каталог | `public_tariff("DIAG")` на момент callback |
| существующий заказ / оплата / отказ | `start_diag_payment_after_yes` / already_paid / blocked |
| состав и цена до ссылки | текст с name/includes/amount; price_changed → без create |
| создание только по явному действию | только sub=`order` |
| ссылка после подтверждённого результата | attachments только при непустом pay_url |
| повтор | sandbox reuse / diag open order; без слепого дубля |
| честный fail | orders_load, catalog_unavailable, no_pay_url, exception |

Код: `_execute_precheck_order` в `primary_doc_precheck_callbacks.py`.  
Sandbox: `PRECHECK_ORDER_SANDBOX=1` или `precheck_order_sandbox` — синтетический `pay.sandbox.local`, без ЮKassa.

**Не** создана вторая платёжная подсистема.

## 2. Browser / API E2E

| Артефакт | Статус |
|---|---|
| API-smoke скрипт | `tools/precheck_e2e/staff_document_check_api_smoke.py` |
| Browser протокол | `docs/ops/sfrfr-111-precheck-browser-smoke.md` |
| Живой admin+API прогон в сессии | **не выполнен** (стенд/token не подняты) |
| PostgREST vs PgRestShim | **разрыв оставлен явно** |

## 3. Изоляция (уже сделано, не переделывали)

Отрицательные тесты: `tests/unit/test_precheck_db_isolation.py`  
Probe без `DATABASE_URL` fallback — подтверждено ранее.

## 4. Live MAX

Сценарий подготовлен: `docs/ops/sfrfr-111-precheck-live-max-scenario.md` — **не запускать**.

## 5. Тестовый реестр

Заполняется сырым логом после коммита на точном SHA (см. `docs/ops/logs/…`).

## 6. Трекер (остатки)

SFRFR-113…117, 111, 110, 100 — открыты; преждевременно не закрывать.
