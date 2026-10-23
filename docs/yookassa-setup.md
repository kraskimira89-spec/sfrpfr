# Настройка ЮKassa для SFRFR

Официальная база: [Документация API ЮKassa](https://yookassa.ru/developers), быстрый старт: [Приём первого платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start).

В SFRFR уже реализован сценарий **Умный платёж (Redirect)** в кабинете клиента и **счёт с короткой ссылкой** для сотрудника:

```text
Сотрудник → «Ссылка» / «В MAX»
      → POST /v3/invoices (delivery self)
      → короткая ссылка https://yookassa.ru/my/i/…
      → QR PNG + кнопка в MAX (только если нажали «В MAX»
         или MAX_PAY_LINK_AUTO_SEND=1 после черновика)
      → webhook payment.succeeded / invoice.paid → paid
```

Документация счетов: [выставление счетов](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics).
SMS и email ЮKassa не включаем — клиенту пишем в MAX.

Канон доставки ссылки/QR: `docs/ops/playbook-pay-link-to-client.md`.
Оркестратор: `issue_and_deliver_pay_link` в `src/sfrfr/services/pay_link.py`.

Клиентский кабинет (как было):

```text
Клиент → POST /api/portal/cases/{case_id}/orders/{order_id}/pay
      → ЮKassa create payment (capture=true)
      → confirmation_url (страница оплаты)
      → return_url (кабинет / mini-app)
      → webhook payment.succeeded → orders/payments + b2c_status
```

## Шаг 0. Что уже есть в коде

| Компонент | Путь |
|---|---|
| Клиент API | `src/sfrfr/integrations/payments/__init__.py` |
| Pay + webhook | `src/sfrfr/api/routes/payments.py` |
| Webhook URL | `POST /api/integrations/payments/yookassa/webhook` |
| Оплата в UI | cabinet «Оплатить онлайн»; admin «Ссылка» / «В MAX» + QR |
| Счета API | `YooKassaClient.create_invoice` + `src/sfrfr/services/pay_link.py` |
| Env | `YOOKASSA_*` в `.env.example` |

## Шаг 1. Личный кабинет ЮKassa

1. Зарегистрируйтесь / войдите: [yookassa.ru](https://yookassa.ru/developers).
2. Создайте **тестовый магазин** (можно без договора — см. [быстрый старт](https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start)).
3. В настройках магазина скопируйте:
   - **shopId** (идентификатор магазина);
   - **Секретный ключ**.
4. Для боя позже: отдельный боевой магазин + договор; не смешивайте ключи test/live.

### Бренд на форме оплаты и в чеке (код vs ЛК)

| Что видит клиент | Где задаётся | Канон SFRFR |
|---|---|---|
| Название магазина / витрина на странице ЮKassa | **Только ЛК ЮKassa** (карточка магазина) — API не меняет | «Проверка стажа» |
| Сайт / ссылка магазина на форме | **Только ЛК ЮKassa** | `https://proverkastaza.ru` |
| Юр. наименование в чеке (ИНН и т.п.) | Договор / карточка магазина в ЛК | ООО «ПОД ПРИСМОТРОМ» (см. `docs/history/requisites-pod-prismotrom.md`) |
| `description` платежа и позиция чека | Код: `payment_description()` / `PAYMENT_PURPOSE` | «Проверка стажа — Диагностика документов» и т.п. |
| `return_url` после оплаты | Код + `YOOKASSA_RETURN_URL` (иначе cabinet / mini-app) | `https://proverkastaza.ru/` |
| Ссылка магазина на форме счёта | **Только ЛК ЮKassa** (счета часто без своего return в UI) | `https://proverkastaza.ru` |

Если на форме всё ещё «такси» / taxi-doroga-dobra — это **не баг API**: владелец меняет название и сайт магазина в [кабинете ЮKassa](https://yookassa.ru/my). В коде return_url legacy taxi переписывается на `proverkastaza.ru`.

### Порядок способов оплаты: СБП → Сбер → ВТБ → остальное

SFRFR использует **Умный платёж** (`confirmation.type=redirect`, без `payment_method_data`) и **счета** (`/v3/invoices`). Это готовая страница ЮKassa, не виджет на нашем сайте.

| Вопрос | Ответ по доке ЮKassa |
|---|---|
| Можно ли задать порядок через `payment_method_types` / `payment_method_data` в create payment? | **Нет.** Для Умного платежа способ в запрос **не** передают — иначе останется один метод, а не список. |
| Где порядок на форме? | Ранжирование ЮKassa (знакомые / популярность) **или настройки магазина** через ЛК / менеджера. API v3 Smart Payment порядок не принимает. |
| Виджет `customization.payment_methods` | Только если перейти на виджет (у нас нет); опция ещё и включается менеджером. |
| Код ВТБ как отдельный способ | В справочнике способов **нет** `vtb`. Есть `sbp`, `sberbank` (SberPay), `bank_card`, `tinkoff_bank`, `alfa_pay`… ВТБ клиент выбирает **внутри СБП** (список банков) или картой. |

**Канон для владельца (желаемый UX):** 1) СБП, 2) SberPay (Сбер), 3) ВТБ (через СБП / «ещё»), 4) остальные в «Подробнее».

**Куда кликнуть / кого попросить:**

1. [ЛК ЮKassa](https://yookassa.ru/my) → нужный магазин → **Настройки → Магазин** ([справка](https://yookassa.ru/docs/support/merchant/payments/settings)).
2. Проверить, что подключены **СБП** и **SberPay**; при необходимости — заявка менеджеру (карандаш / обращение, часто до 3 раб. дней).
3. Написать в поддержку / менеджеру ЮKassa (`ecommerce@yoomoney.ru` или чат ЛК):  
   *«Нужен порядок способов на странице Умного платежа и счетов: СБП → SberPay → остальные (ВТБ внутри СБП). Ранжирование по настройкам магазина, не только по популярности.»*
4. Кодом мы **не** передаём `payment_method_data` и держим `capture=true` (иначе СБП на форме не появится).

## Шаг 2. Переменные на VPS / `.env`

```env
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
YOOKASSA_API_BASE=https://api.yookassa.ru/v3
# Куда вернуть клиента после оплаты (опционально; иначе cabinet/mini-app)
YOOKASSA_RETURN_URL=https://proverkastaza.ru/
# Чеки 54-ФЗ: true, если в магазине включена фискализация
YOOKASSA_SEND_RECEIPT=true
# Тест: секрет test_… → в ЮKassa уходит 1 ₽ (см. шаг 4)
PAYMENT_TEST_AMOUNT_RUB=1
PAYMENT_TEST_AMOUNT_ENABLED=0
CABINET_PUBLIC_URL=https://cabinet.proverkastaza.ru
MAX_MINIAPP_URL=https://proverkastaza.ru/app/
PUBLIC_BASE_URL=https://api.proverkastaza.ru
```

Перезапустите API (`sfrfr-api` / systemd).

Проверка: `GET /v3/me` → `status=enabled`. Без ключей `POST .../pay` → **503**.  
Без email при `SEND_RECEIPT=true` → **400**.  
Фискализация вкл. + `SEND_RECEIPT=false` → ЮKassa `Receipt is missing or illegal`.

## Шаг 3. HTTP-уведомления (webhook)

По [входящим уведомлениям](https://yookassa.ru/developers/using-api/webhooks):

1. ЛК ЮKassa → магазин → **Интеграция** → HTTP-уведомления.
2. URL (предпочтительно с `/webhook`; без суффикса тоже принимается):

```text
https://api.proverkastaza.ru/api/integrations/payments/yookassa/webhook
```

или короткий алиас:

```text
https://api.proverkastaza.ru/api/integrations/payments/yookassa
```

События минимум: `payment.succeeded`; желательно `payment.canceled`, `payment.waiting_for_capture`, `invoice.paid`.
`refund.succeeded` / `payment.method.active` можно оставить включёнными — лишние события без payment id будут `ignored`/400 без падения оплаты.

Без webhook статус в кабинете обновится только вручную / при повторной проверке; клиент после оплаты увидит `return_url`, но «оплачено» надёжно ставит webhook.

## Шаг 4. Тестовый платёж (по доке)

### Сумма 1 ₽ в тестовом магазине

| Условие | Сумма в `create payment` / `invoice` |
|---|---|
| `YOOKASSA_SECRET_KEY` начинается с `test_` | **`PAYMENT_TEST_AMOUNT_RUB`** (канон **1.00**) |
| Live-ключ (`live_…`), флаг выкл. | `orders.amount_rub` (3000 / 5000 / 8000) |
| `PAYMENT_TEST_AMOUNT_ENABLED=1` | принудительно test-сумма (даже на live — только отладка) |
| `PAYMENT_TEST_AMOUNT_RUB=0` | override выключен |

Код: `yookassa_charge_amount_rub` в `src/sfrfr/services/payment_amount.py`.  
**Не** меняет `PUBLIC_TARIFFS`, витрину `/tarify/` и сумму в заказе — только запрос к ЮKassa.

На VPS после смены env: перезапуск `sfrfr-api` (systemd). Секрет test/live — в `.env`, не в git.

1. В admin создайте заказ `DIAG` / `ACCOMP` на дело (сумма > 0; в UI остаётся тариф).
2. В cabinet или mini-app нажмите **Оплатить онлайн** (на test-ключе в ЮKassa будет **1 ₽**).
3. Откроется `confirmation_url` ЮKassa.
4. Тестовая карта (из [быстрого старта](https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start)):

```text
5555 5555 5555 4444
CVC: любой
Срок: любой будущий
```

5. После оплаты клиент вернётся на `return_url` (`?case=&view=payments&paid=1`).
6. Webhook → `payments.status=succeeded`, `orders.status=paid`, `b2c_status`:
   - `DIAG` → `diagnostic_paid`
   - `ACCOMP` → `service_paid`
   - `SF_*` → `success_fee_paid`
7. При **первом** `succeeded`: уведомление клиенту в MAX (если привязан) + системное сообщение в деле; при `AMOCRM_ENABLED=1` — sync сделки + заметка «оплата прошла» (не чек). Фискальный чек — только ЮKassa → Evotor → ОФД.

### ЛК: «Способ подключения» ≠ доставщик чеков

В настройках магазина (`/my/shop-settings`) поле **«Способ подключения к ЮKassa»** — это **метка онбординга** (CMS/модуль), не канал фискализации.

| Поле в ЛК (ShopID `1417002`) | Смысл | Что делать |
|---|---|---|
| Способ подключения = `AmoCRM` | Старый контур / виджет amo | **Не** влияет на `receipt` из нашего API. Сменить метку → заявка менеджеру (карандаш / `ecommerce@yoomoney.ru`), без смены ключей и webhook |
| Протокол = `API` | Реальная интеграция платежей | **Оставить.** Канон SFRFR |
| Онлайн-касса / Evotor | Доставка данных чека в ККТ | Держать кассу **онлайн**; иначе письмо «пробейте вручную» |

Черновик заявки в поддержку ЮKassa (копипаст):

```text
ShopID 1417002. Просьба сменить «Способ подключения к ЮKassa» с AmoCRM на API / собственная интеграция.
Протокол уже API; платежи и webhook работают через наш бэкенд (не виджет amoCRM).
Фискализация: сторонняя ККТ Evotor + receipt в create payment. Ключи и URL webhook не менять.
```

## Шаг 5. Чеки 54-ФЗ и ОФД (канон SFRFR)

Обзор режимов: [54-ФЗ в ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics).

### Канонический контур (без конфликта)

У боевого магазина SFRFR (`GET /v3/me`): `fiscalization.provider = evotor` — **своя ККТ-партнёр**, не сервис «Чеки от ЮKassa».

```text
Оплата ЮKassa
  → SFRFR передаёт receipt (email + позиции)   YOOKASSA_SEND_RECEIPT=true
  → касса Evotor пробивает чек
  → ОФД «Платформа ОФД» → ФНС + клиент
       ЛК: https://lk.platformaofd.ru/
```

| Слой | Задействовать | Не задействовать |
|---|---|---|
| ЮKassa ЛК | Один канал: **онлайн-касса / Evotor** | Параллельно «Чеки от ЮKassa» |
| SFRFR | `YOOKASSA_SEND_RECEIPT=true` + email | Фискальный чек через MAX / amoCRM |
| Платформа ОФД | Просмотр чеков, выгрузки | Второй «кассир» на тот же платёж |
| Evotor | Одна касса, привязанная к магазину | Ручной повторный пробив того же payment |

Проверка контура:

```bash
python -m sfrfr yookassa-status
# ожидание: fiscal_provider=evotor, send_receipt=true, warnings=[]
```

### Настройка в коде

1. В `.env`: `YOOKASSA_SEND_RECEIPT=true` (обязательно при `fiscalization_enabled`).
2. У клиента — **email или телефон** (профиль / `customer_email` в `/pay`). Без контакта ссылку/платёж с чеком не создаём.
3. Код передаёт `receipt.customer` + `items` + `internet=true`, `vat_code` из `YOOKASSA_VAT_CODE` (по умолчанию `1`).
4. Если Evotor не принял чек (`receipt_registration` ≠ succeeded) — webhook вызывает `POST /v3/receipts`; вручную:  
   `python -m sfrfr yookassa-retry-receipt <payment_id> --email client@example.com`

**Не отправляйте фискальный чек через MAX или amoCRM** — это не ОФД.  
После оплаты SFRFR шлёт в MAX/чат дела сервисное «оплата получена, чек на email»; заметка в amo — только если `AMOCRM_ENABLED=1` (сейчас выключен).

Пока `SEND_RECEIPT=false` при включённой фискализации ЮKassa вернёт `Receipt is missing or illegal`.

Касса Evotor должна быть **включена и в сети** — иначе ЮKassa пришлёт письмо «пробейте вручную» даже при корректном API.

## Шаг 6. Боевой режим

1. Договор и верификация магазина в ЮKassa.
2. Замените `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY` на **боевые**.
3. Webhook тот же URL (или отдельный, если два магазина).
4. Проверьте один реальный платёж на минимальную сумму и возврат при необходимости.

## Соответствие шагам ЮKassa ↔ SFRFR

| Шаг из доки | Как у нас |
|---|---|
| 1. Создать платёж (`capture: true`, redirect) | `YooKassaClient.create_payment` |
| 2. Отправить на `confirmation_url` | UI открывает URL из `/pay` |
| 3. Дождаться `succeeded` | Webhook `yookassa_webhook` |

Аутентификация API: Basic Auth `shopId:secretKey` + заголовок `Idempotence-Key` — как в [основах API](https://yookassa.ru/developers).

## Частые ошибки

| Симптом | Что проверить |
|---|---|
| 503 на `/pay` | Пустые `YOOKASSA_SHOP_ID` / `SECRET_KEY` на VPS |
| 502 yookassa create failed | Неверный ключ, сумма 0, ответ API в логах |
| Оплатил, статус pending | Webhook URL / HTTPS / firewall; событие `payment.succeeded` |
| Нет чека | `YOOKASSA_SEND_RECEIPT` и email/телефон клиента; ЛК [Платформа ОФД](https://lk.platformaofd.ru/); Evotor онлайн |
| Письмо «пробейте вручную» / чек не доставлен в ККТ | Evotor выкл./офлайн **или** неверный `vat_code`. Повтор: `sfrfr yookassa-retry-receipt <payment_id> --email …`. Webhook сам ретраит `/receipts` |
| `Receipt is missing` | Фискализация вкл., а `SEND_RECEIPT=false` |
| Двойной чек | В ЮKassa два режима сразу или ручной пробив в Evotor + API |
| Тест не проходит | Используете боевой ключ или наоборот |
| После оплаты редирект на taxi / «дорога добра» | 1) VPS `YOOKASSA_RETURN_URL=https://proverkastaza.ru/` + рестарт API; 2) ЛК ЮKassa → магазин → сайт `https://proverkastaza.ru` (для счетов без API return) |
| На форме/в шапке «дорога добра» / taxi / старый сайт | ЛК ЮKassa → название и сайт магазина → «Проверка стажа», `proverkastaza.ru` (не правится кодом) |
| В позиции чека нет «Проверка стажа» | Новый платёж после деплоя; `payment_description` / `PAYMENT_PURPOSE` |
| На форме не тот порядок (не СБП первым) | Только ЛК/менеджер ЮKassa; в API Smart Payment порядка нет (см. выше) |
| Нет СБП на форме | `capture` должен быть `true`; способ СБП подключён в магазине |

## Минимальный чеклист приёмки

- [ ] `python -m sfrfr yookassa-status` → `evotor`, `SEND_RECEIPT=true`, без warnings
- [ ] В ЛК ЮKassa только один канал фискализации (ККТ, не дубль с «Чеки от ЮKassa»)
- [ ] Webhook HTTPS настроен в ЛК
- [ ] Создан заказ на деле
- [ ] Оплата (тест/минимальная сумма) → один чек в [Платформа ОФД](https://lk.platformaofd.ru/)
- [ ] После webhook заказ `paid` в кабинете; MAX/amo — сервисное уведомление, не чек
- [ ] Return URL открывает нужный канал (cabinet / mini-app)
