# Контрольная точка цикла 5 (исполнитель)

**PR:** [#269](https://github.com/kraskimira89-spec/sfrpfr/pull/269)  
**Auto-merge:** OFF  
**Merge / deploy / live MAX / реальные платежи / закрытие SFRFR-110/111:** нет

## 1. База и окружение

| Поле | Значение |
|---|---|
| Код order+sandbox | `2c5c0fd2` (+ mypy `e03ea58a`) |
| Стенд | `tools/precheck_job_pg`: PG `:55432`, PostgREST `:55433` |
| Credentials | `sfrfr` / БД `sfrfr_precheck` / JWT secret local-only |
| Live MAX | выключен |
| ЮKassa | sandbox `PRECHECK_ORDER_SANDBOX=1` или mock в unit |

## 2. Доступ к БД (граница shim)

| Путь | Статус |
|---|---|
| PgRestShim + psycopg | suite `test_precheck_job_pg.py` (остаётся) |
| **Реальный PostgREST** `postgrest/postgrest:v12.2.8` | `tests/integration/test_precheck_job_postgrest.py` |
| Клиент | `SyncPostgrestClient` + `.table()`-обёртка (тот же HTTP/CAS, что supabase postgrest) |
| GoTrue / полный Supabase URL `/rest/v1` на cloud | **не** в этом стенде |

Формулировка: PG reclaim через shim **не** заменяет PostgREST; цикл 5 добавил отдельный набор на живом PostgREST. Полный cloud Supabase Auth+Storage для browser login — отдельный остаток.

## 3. `precheck:order`

| Свойство | Доказательство |
|---|---|
| Существующий DIAG-маршрут | `_execute_precheck_order` → `start_diag_payment_after_yes` |
| Не вторая платёжка | да |
| Каталог / price_changed | unit |
| already_paid / orders_load | unit |
| Sandbox без ЮKassa | unit + `pay.sandbox.local` |
| Повтор / reuse | sandbox reused |
| Ссылка только при pay_url | `precheck_order_no_pay_url` |
| offer_info ≠ create | отдельный sub |

Больше не `unavailable` / не только cabinet-handoff.

## 4. Browser E2E

| Элемент | Статус |
|---|---|
| Протокол | `docs/ops/sfrfr-111-precheck-browser-smoke.md` |
| API-smoke скрипт | `tools/precheck_e2e/staff_document_check_api_smoke.py` |
| Enqueue+dedupe на PostgREST | `test_postgrest_enqueue_dedupe_real_rest` |
| Полный browser (логин сотрудника → UI) | **блокер:** нет GoTrue/Auth на стенде; штатный admin требует Bearer JWT от Supabase Auth. Не снижаем критерий — фиксируем причину. |

Подмены для будущего browser: OCR/LLM/MAX-transport/YooKassa — контролируемые адаптеры; перечислить в отчёте прогона.

## 5. Тестовый реестр (разнести с CI)

Сырые прогоны — отдельные файлы в `docs/ops/logs/`.  
CI GitHub — отдельный прогон на head (не смешивать с pytest-счётчиком).

## 6. Трекер

Обновляется live MCP в конце цикла. SFRFR-110/111/112–117 **не закрывать**.

## 7. Live MAX

Сценарий: `docs/ops/sfrfr-111-precheck-live-max-scenario.md` — не выполнять.
