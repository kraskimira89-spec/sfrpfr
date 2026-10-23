# 2026-10-23 — smoke дедуп #226 (1 ₽) перед повторным SUPPORT 8000

**Вердикт: ✅ PASS → `BLOCKER_CLEARED`**

Владелец: возвраты 3/5/8k получены → «для 8000 прогоняем 1р» → «оплатил».

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
| Вердикт | **PASS** → `BLOCKER_CLEARED` |

## Оговорка Стратега

PASS на 1₽ = «дубль не повторился на этом платеже», не полное доказательство закрытия гонки webhook×pending. Боевой SUPPORT 8000 — только по отдельному «да, платим 8000».

## Следующий шаг

Ждать «да, платим 8000». Коррекция лишнего FD 778 (после возврата 8000 остался +8000 в ОФД) — с бухгалтером.
