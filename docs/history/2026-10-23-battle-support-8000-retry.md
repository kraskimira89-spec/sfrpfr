# 2026-10-23 — повторный SUPPORT 8000 ₽ (после FAIL+refund+#226)

**Вердикт: ✅ PASS** (1× `type=payment`; дубля нет)

Владелец: «да, платим 8000» (остаточный риск гонки принят) → «смена открыта. оплатил».

## Создание

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | **0** (после оплаты **0**) |
| Тариф | ACCOMP / SUPPORT — «Шаг 3. Сопровождение до подачи» |
| Дело | **ПС-786706** `1322ee50-6183-4662-8511-76e7f81c0112` (`is_test`) |
| Order | `8c468c1d-d2aa-40f5-a981-49245087db39` → **paid** |
| Invoice | `in-326d8ed9-0000-0050-5742-02ce2df1850f` → succeeded |
| Pay URL | `https://yookassa.ru/my/i/att7GUuC3kEO/a` |
| Email | nataliylo@yandex.ru |
| Второй счёт | **не** создавался |

## После оплаты

| Критерий | Результат |
|----------|-----------|
| Webhook → 200 | ✅ 77.75.154.206, **18:22:43 +03** |
| Order paid без reconcile | ✅ |
| Ровно 1 payments | ✅ `326d8f33-000f-5001-9000-14edf85c8cb0` succeeded |
| `receipt_registration` | **succeeded** |
| receipts `type=payment` | ✅ **ровно 1** succeeded |
| settlements | **нет** (авточек invoice, не ensure) |
| Сумма | **8000.00** |
| Receipt | `ra-326d8f83-0001-0050-5840-1207128dc861` |
| FD в API | `null` (Evotor/ОФД) |
| ENABLED=0 | ✅ |
| ensure/skipped в journal | записей нет (webhook при уже succeeded) |

## Контекст

Первый SUPPORT 8000 (`326d821f…`) — FAIL дубль FD 777+778, возврат сделан; лишний FD 778 в ОФД — бухгалтер.
На retry дубль **не** повторился. Live-гонка pending по-прежнему не воспроизводилась на этом платеже.
