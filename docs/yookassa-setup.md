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
YOOKASSA_RETURN_URL=https://cabinet.proverkastaza.ru/
# Чеки 54-ФЗ: true, если в магазине включена фискализация
YOOKASSA_SEND_RECEIPT=true
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
2. URL:

```text
https://api.proverkastaza.ru/api/integrations/payments/yookassa/webhook
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
7. При **первом** `succeeded`: уведомление клиенту в MAX (если привязан) + системное сообщение в деле; в amoCRM — sync сделки + заметка «оплата прошла». Фискальный чек по-прежнему только через ЮKassa/ОФД.

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
2. У клиента — **email** (профиль или `customer_email` в `/pay`).
3. Код передаёт `receipt.customer` + `items` с `vat_code` (по умолчанию `1`).

**Не отправляйте фискальный чек через MAX или amoCRM** — это не ОФД.  
После оплаты SFRFR шлёт в MAX/чат дела сервисное «оплата получена, чек на email», а в amo — служебную заметку.

Пока `SEND_RECEIPT=false` при включённой фискализации ЮKassa вернёт `Receipt is missing or illegal`.

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
| Нет чека | `YOOKASSA_SEND_RECEIPT` и email клиента; ЛК [Платформа ОФД](https://lk.platformaofd.ru/) |
| `Receipt is missing` | Фискализация вкл., а `SEND_RECEIPT=false` |
| Двойной чек | В ЮKassa два режима сразу или ручной пробив в Evotor + API |
| Тест не проходит | Используете боевой ключ или наоборот |

## Минимальный чеклист приёмки

- [ ] `python -m sfrfr yookassa-status` → `evotor`, `SEND_RECEIPT=true`, без warnings
- [ ] В ЛК ЮKassa только один канал фискализации (ККТ, не дубль с «Чеки от ЮKassa»)
- [ ] Webhook HTTPS настроен в ЛК
- [ ] Создан заказ на деле
- [ ] Оплата (тест/минимальная сумма) → один чек в [Платформа ОФД](https://lk.platformaofd.ru/)
- [ ] После webhook заказ `paid` в кабинете; MAX/amo — сервисное уведомление, не чек
- [ ] Return URL открывает нужный канал (cabinet / mini-app)
