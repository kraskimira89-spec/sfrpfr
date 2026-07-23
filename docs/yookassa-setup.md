# Настройка ЮKassa для SFRFR

Официальная база: [Документация API ЮKassa](https://yookassa.ru/developers), быстрый старт: [Приём первого платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start).

В SFRFR уже реализован сценарий **Умный платёж (Redirect)**:

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
| Оплата в UI | cabinet «Оплатить онлайн», mini-app вкладка «Оплаты» |
| Env | `YOOKASSA_*` в `.env.example` |

## Шаг 1. Личный кабинет ЮKassa

1. Зарегистрируйтесь / войдите: [yookassa.ru](https://yookassa.ru/developers).
2. Создайте **тестовый магазин** (можно без договора — см. [быстрый старт](https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start)).
3. В настройках магазина скопируйте:
   - **shopId** (идентификатор магазина);
   - **Секретный ключ**.
4. Для боя позже: отдельный боевой магазин + договор; не смешивайте ключи test/live.

## Шаг 2. Переменные на VPS / `.env`

```env
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
YOOKASSA_API_BASE=https://api.yookassa.ru/v3
# Куда вернуть клиента после оплаты (опционально; иначе cabinet/mini-app)
YOOKASSA_RETURN_URL=https://cabinet.taxi-doroga-dobra.ru/
# Чеки 54-ФЗ через ЮKassa (нужен email клиента)
YOOKASSA_SEND_RECEIPT=false
CABINET_PUBLIC_URL=https://cabinet.taxi-doroga-dobra.ru
MAX_MINIAPP_URL=https://taxi-doroga-dobra.ru/app/
PUBLIC_BASE_URL=https://api.taxi-doroga-dobra.ru
```

Перезапустите API (`sfrfr-api` / systemd).

Проверка: без ключей `POST .../pay` вернёт **503** `payment provider not configured`.

## Шаг 3. HTTP-уведомления (webhook)

По [входящим уведомлениям](https://yookassa.ru/developers/using-api/webhooks):

1. ЛК ЮKassa → магазин → **Интеграция** → HTTP-уведомления.
2. URL:

```text
https://api.taxi-doroga-dobra.ru/api/integrations/payments/yookassa/webhook
```

3. События минимум: `payment.succeeded`, желательно `payment.canceled`, `payment.waiting_for_capture`.
4. URL должен быть **HTTPS** и отвечать **200** быстро (наш handler так и делает).

Без webhook статус в кабинете обновится только вручную / при повторной проверке; клиент после оплаты увидит `return_url`, но «оплачено» надёжно ставит webhook.

## Шаг 4. Тестовый платёж (по доке)

1. В admin создайте заказ `DIAG` / `ACCOMP` на дело (сумма > 0).
2. В cabinet или mini-app нажмите **Оплатить онлайн**.
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

## Шаг 5. Чеки 54-ФЗ (когда понадобится)

Документация: [Чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics).

1. В ЛК включите отправку чеков (или свою ОФД).
2. В `.env`: `YOOKASSA_SEND_RECEIPT=true`.
3. У клиента должен быть **email** (из JWT/профиля или `customer_email` в теле pay).
4. Код передаёт `receipt.customer` + `items` с `vat_code` (по умолчанию `1`).

Пока `false` — платежи без блока `receipt` (удобно для теста API).

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
| Нет чека | `YOOKASSA_SEND_RECEIPT` и email клиента |
| Тест не проходит | Используете боевой ключ или наоборот |

## Минимальный чеклист приёмки

- [ ] Test shopId + secret в `.env` на VPS
- [ ] Webhook HTTPS настроен в ЛК
- [ ] Создан заказ на деле
- [ ] Оплата тестовой картой `5555…4444`
- [ ] После webhook заказ `paid` в кабинете
- [ ] Return URL открывает нужный канал (cabinet / mini-app)
