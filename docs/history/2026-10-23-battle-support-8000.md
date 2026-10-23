# 2026-10-23 — боевой SUPPORT 8000 ₽ (shop 1421177)

**Вердикт: ❌ FAIL — `FAIL_DUP_RECEIPT` (блокер SFRFR-89)**

Владелец: «да, платим 8000» → «оплатил». Деньги **оставить** (возврат позже).
DIAG FD **775** + DOCS FD **776** PASS. Пакет: **ACCOMP / SUPPORT**.
Боевой прогон **стоп** до фикса дублей + повторного smoke.

## Предусловия

| Проверка | Факт |
|----------|------|
| Shop | **1421177** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | **0** (после оплаты остался **0**) |
| Email клиента до счёта | **nataliylo@yandex.ru** (телефон сохранён) |
| Граница тарифа | `package_code=ACCOMP`, classify=**SUPPORT**, «Шаг 3. Сопровождение до подачи» |

## Дело / счёт

| Поле | Значение |
|------|----------|
| Дело | **ПС-786706** (`1322ee50-…0112`, `is_test`) |
| Order | `af921028-…82cd` → **paid**, **8000.00** |
| Charge API | **8000.00** (flag=0) |
| Pay URL | `https://yookassa.ru/my/i/attt2IxThoEQ/a` |
| Payment id | `326d821f-000f-5001-9000-1a272330e2d3` |
| Paid at UTC | 2026-10-23T14:26:23Z (webhook 17:26:23 +03) |
| Второй счёт | **не** создавался |

## Критерии после оплаты

| Критерий | Статус |
|----------|--------|
| Apache `POST …/yookassa/webhook` **200** (77.75.154.206, 17:26:23 +03) | ✅ |
| order **paid** без ручного reconcile | ✅ |
| ровно **1** `payments` (`succeeded`) | ✅ |
| `GET /receipts` → **1×** `type=payment` succeeded | ❌ **2×** succeeded |
| Сумма позиции **8000.00** | ✅ (на обоих чеках) |
| FD | **777** + **778** (дубль) |
| `receipt_registration` | **succeeded** |
| `PAYMENT_TEST_AMOUNT_ENABLED=0` | ✅ |
| Case `service_paid`, next=«Сопровождение до подачи — план для клиента» | ✅ (статус дела ок; критерий чека — нет) |

### Чеки (дубль)

| Receipt | type | status | FD | amount |
|---------|------|--------|----|--------|
| `ra-326d824f-…136b` | payment | succeeded | **777** | 8000.00 |
| `ra-326d8251-…93e5` | payment | succeeded | **778** | 8000.00 |

Refund = 0. Один `payment_id`, два succeeded `type=payment` → **жёсткий блокер** по плану.

## Email / чек клиенту

| Факт | Значение |
|------|----------|
| `clients.email` | **nataliylo@yandex.ru** |
| Телефон | `+79001113344` (не затёрт) |
| Создание счёта | email выставлен **до** `create_invoice` (в payload `customer_email`) |
| `GET /receipts` → `customer.email` | **null** в ответе API (оба чека; phone тоже null — типично для list) |
| `receipt_registration` | **succeeded** |
| Notify в деле / `notification_jobs` | **не** найдено записи «чек на email» |
| Логи create payload | в `api.log` / journal за окно оплаты явного дампа `customer.email` нет |

Вывод по email: контакт на клиенте и путь в create — ок; доставка чека на почту по API receipts не подтверждается полями customer; отдельного notify в БД нет.

## Root cause (расследование)

| FD | Receipt id | Источник | Доказательство |
|----|------------|----------|----------------|
| **777** | `ra-326d824f-…136b` | авточек из `create_invoice` → `payment_data.receipt` | **нет** `settlements` (как SMOKE/DIAG/DOCS) |
| **778** | `ra-326d8251-…93e5` | webhook → `ensure_payment_receipt` → `POST /v3/receipts` | **есть** `settlements: cashless` (только наш `create_receipt`) |

Timeline (UTC): payment `created_at` 14:25:35 → `captured_at`/`webhook` 14:26:23 → оба FD `registered_at` 11:26:00 (минута Evotor/ОФД, без секунд). Один webhook 200. Email `@yandex.ru` vs `@example.invalid` на путь дубля **не** влияет (fingerprint settlements).

Гонка: webhook при `receipt_registration=pending` (или пусто) вызывал ensure; `GET /receipts` ещё пуст → второй create. SUPPORT не особый тариф — та же invoice-схема, что DOCS.

Фикс: webhook retry только при `canceled`; ensure skip при `reg=pending` (PR **#226**). Коррекцию лишнего FD **не** делаем без бухгалтера / «да, возвращаем».

**Пробел:** нет job reconcile для «webhook видел `pending`, позже `canceled`». Workaround: CLI `yookassa-retry-receipt` / письмо ЮKassa. Follow-up в SFRFR-89 — не гадать код до smoke.

## Стоп

- Не создавать новые боевые счета.
- Статус прогона: **`BLOCKED_DUP_RECEIPT`** → после деплоя фикса: `FIX_IN_FLIGHT` / smoke 1₽.
- Блокер: **SFRFR-89** (дубль FD 777/778 на `326d821f…`).
- Возврат / правка кассы — только по решению владельца после фикса.
