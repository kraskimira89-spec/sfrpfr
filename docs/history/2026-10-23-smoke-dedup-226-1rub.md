# 2026-10-23 — smoke дедуп #226 (1 ₽) перед повторным SUPPORT 8000

**Вердикт: ✅ PASS по формальному критерию smoke; статус плана — `SMOKE_OK_RACE_UNVERIFIED` (не полный `BLOCKER_CLEARED`)**

Владелец: возвраты 3/5/8k получены → «для 8000 прогоняем 1р» → «оплатил».
Стратег: ветка `pending` на этом платеже **не** сработала (ensure/skipped в логах нет).

## Создание

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | **0** (не включали; после оплаты **0**) |
| Amount | **1.00** RUB |
| Payment id | `326d88ae-000f-5001-9000-1b6e2eb6d4fc` |
| Confirmation | `https://yoomoney.ru/checkout/payments/v2/contract?orderId=326d88ae-…` |
| receipt email | `nataliylo@yandex.ru` |
| metadata | `channel=smoke_dedup_226` |
| Фикс на VPS | #226 `should_auto_retry_fiscal_receipt` / ensure skip `pending` |
| Второй счёт | **не** создавался |

## После оплаты

| Критерий | Результат |
|----------|-----------|
| Payment status | **succeeded** / paid |
| Webhook | ✅ `POST …/yookassa/webhook` **200** (77.75.153.78, 17:55:04 +03) |
| `receipt_registration` | **succeeded** |
| `GET /receipts` total | **1** |
| `type=payment` succeeded\|pending | **ровно 1** |
| `type=refund` | 0 |
| settlements на чеке | **нет** (= авточек create_payment, не ensure) |
| Receipt id | `ra-326d8908-0003-0050-2856-75c4ce42144c` |
| FD в API | `null` (смотреть Evotor/ОФД; как у части чеков магазина) |
| ENABLED | **0** |
| Вердикт smoke | **PASS** (дубль не повторился) |
| Статус плана | `SMOKE_OK_RACE_UNVERIFIED` (гонка live не проверена) |

## Оговорка Стратега

PASS на 1₽ = «дубль не повторился», **не** «фикс гонки доказан в бою». Платежи 774–776 давали тот же результат до #226.

## Проверка ветки pending (без нового платежа)

HTTP webhook-тест: `test_webhook_http_pending_does_not_call_ensure_or_create_receipt` — при `receipt_registration=pending` ensure/create_receipt **не** вызываются → статус `PENDING_PATH_HTTP_VERIFIED`. Живая задержка кассы / закрытая смена — отдельно, по решению владельца.

## Следующий шаг

Повторный SUPPORT 8000 — только «да, платим 8000» с учётом оговорки. Коррекция FD 778 — с бухгалтером.
