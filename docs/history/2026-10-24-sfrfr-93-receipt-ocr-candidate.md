# 2026-10-24 — SFRFR-93: OCR-кандидат в fiscal reconcile

**Окно наблюдения:** старт `2026-10-23T21:01:27Z` → отметка `2026-10-24T21:01:27Z` (не сбрасывали).
Строку платежа **не** правили вручную. Полные UUID / ПДн сюда **не** кладём.

## Цепочка (факт кода)

```text
confirm_order_from_receipt
  → create_payment_record(provider=receipt_ocr, id=receipt:{doc|order})
  → apply_provider_payment(succeeded)
  → list_succeeded_payments_for_reconcile / list_payments_for_stale_fiscal_alert
       select RECONCILE_PAYMENT_COLUMNS (вкл. provider, provider_payment_id)
       PostgREST limit → затем Python filter_* (OCR-исключение)
  → process_payment_reconcile: lease → fetch_payment → list/gate → create
  → stale: _maybe_alert(stale_48h)
```

До патча OCR доходил до `fetch_payment` → `error_before_post`, create не вызывался.

## Этап А — границы

| Вопрос | Ответ |
|---|---|
| Providers в платёжных сценариях | Писатели: **`yookassa`** (pay_link / case_repository), **`receipt_ocr`** (`confirm_order_from_receipt`). `provider=receipt` в коде **не** пишется (защитный алиас в фильтре). |
| Поля выборки | `RECONCILE_PAYMENT_COLUMNS`: id, order_id, status, **provider**, **provider_payment_id**, fiscal_*, paid/created, reconcile_* (без post_payload PII) |
| Где exclude | `provider_payment_passes_ocr_exclusions` в `filter_reconcile_candidates` и `filter_stale_alert_candidates`; оба list_* зовут фильтр **до** lease/fetch/alert |
| Другие OCR | На диагностике: 1 строка `receipt:%` / `receipt_ocr`. Live DB re-check 2026-10-24: MCP Supabase **unreachable** — повтор после сети |
| Лимит до фильтра | `.limit(N)` в PostgREST **до** Python-фильтра → OCR-строки могут вытеснять ЮKassa из страницы. Риск остаточный; SQL-exclude — отдельный follow-up |

## Снимок дефектной строки (обезличено)

| Поле | Значение |
|---|---|
| payment.id | `89be641d…` |
| provider | `receipt_ocr` |
| provider_payment_id | `receipt:{order}` |
| fiscal_status | NULL |
| attempts / streak / post / alert | 0 / 2 / NULL / NULL |
| Тики (MSK) | ~15:01, ~15:11 → candidates=1, error_before_post |

## Контракт фильтра

`provider_payment_passes_ocr_exclusions` — **exclude known OCR**, не whitelist ЮKassa:

- False: `receipt_ocr` \| `receipt`; пустой id; id с префиксом `receipt:`
- True: иначе (не доказательство yookassa)

Алиас имени `provider_payment_is_yookassa_reconcile_target` сохранён (= та же функция).

## Таблица тестов (#260)

| Проверка | Ожидание | Где |
|---|---|---|
| receipt_ocr + receipt: | исключён | queries |
| receipt_ocr + обычный ID | исключён | queries |
| yookassa + receipt: | исключён | queries |
| пустой/other + receipt: | исключён | queries |
| пустой ID | исключён | queries |
| provider=receipt | исключён | queries |
| yookassa нормальный | reconcile + stale кандидат | queries |
| mixed OCR+YK list repo | только YK; select несёт provider | queries |
| tick hybrid OCR+YK | lease/fetch только YK; OCR без update/claim/create | job |

## Ограничения / не сделано без согласования

- merge/deploy, правка строки БД, чеки, MAX, `.env`/timer
- whitelist provider; SQL-фильтр OCR (crowding)
- постфикс-тики после выкладки — этап Д

## Меры

Патч #260; после deploy — ≥3 тика без OCR-кандидата; 24ч-итог с разделением периодов.
