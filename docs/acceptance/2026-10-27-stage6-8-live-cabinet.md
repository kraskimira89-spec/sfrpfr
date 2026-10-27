# Живой проход ступеней 6–8 (кабинет)

**Дата:** 2026-10-27  
**Дело:** `1579e69f-f74f-4c38-9fb1-c65493afe3c4`  
**SHA на момент прогона:** `da94a1e1` (#349); после находки дубля — фикс API в отдельном PR.

## Результаты

| # | Проверка | Результат | Доказательство |
|---|---|---|---|
| 6 | Согласие на обращения ≠ согласование разбора | **PASS** | UI «Согласен» → notice + audit `appeals_consent_accepted` `12:03:03Z`; этап 5 без `full_analysis_approved`, статус разбора не менялся |
| 7a | Счёт 5 000 после согласия | **PASS** | UI создал pending + `invoice_sent`; API create 201 |
| 7b | Повторный счёт в UI | **PASS** (disabled при открытом счёте) | кнопка disabled в коде #349 |
| 7c | Повторный счёт API | **FAIL → FIX** | на live оба POST дали 201 (два pending). Гейт `has_open_or_paid_docs_order` добавлен |
| 7d | Paid → ступень done | **unit PASS** | live: оставлен 1× pending (боевую оплату не гоняли) |
| 8 | «Пакет готов» ≠ «Передан клиенту» | **PASS** | audit `appeals_package_ready` `12:04:22Z` и `appeals_package_delivered` `12:04:23Z`, один `actor_id` staff |
| 9 | Передача ≠ подача | **PASS** | `hasSubmissionConfirm=false`; pipeline/b2c не стали submission |

## Уборка тестовых дублей

Отменены лишние ACCOMP 5000 (`duplicate`); оставлен один pending для наблюдения ступени 7.

## Вне прогона

Этап 5 и доп. документы не трогали. Боевая оплата 5000 не проводилась.
