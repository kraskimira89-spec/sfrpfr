# Как клиенту уходит ссылка / QR на оплату ЮKassa

Канон SFRFR: **канал доставки — MAX** (личный чат с ботом). SMS и email ЮKassa не включаем.

## Что получает клиент

В одном сообщении MAX:

1. Текст со суммой и короткой ссылкой `https://yookassa.ru/my/i/…`
2. Кнопка **«Оплатить»** (inline link → та же `pay_url`)
3. Картинка **QR** (PNG с нашего API: `GET /api/public/pay/{order_id}/qr.png?s=…`)

После оплаты по ссылке чек в чат не нужен. Перевод вручную — фото чека в MAX или кабинет.

Secure action link для оплаты **не** используем: страница оплаты на стороне ЮKassa.

## Каналы (кто инициирует)

| Канал | Как | Результат |
|---|---|---|
| Staff **«В MAX»** | Admin → Финансы → `POST .../admin/orders/{id}/pay-link` `send_max=true` | Invoice + MAX (кнопка+QR) |
| Staff **«Ссылка»** | То же API, `send_max=false` | Только `pay_url` / QR в карточке (копипаст) |
| Staff **напоминание** | `POST .../remind` `send_max=true` | Снова кнопка+QR; если ссылки нет — сначала выставит счёт |
| **Авто** (флаг) | `MAX_PAY_LINK_AUTO_SEND=1` после черновика счёта | То же, что «В MAX», без клика staff |
| **Чат-бот** | `CASE_CHAT_PAY_LINK_ENABLED=1` + счёт готов + вопрос об оплате | Invoice + сообщение в единый чат (MAX и кабинет) |
| Клиент сам | Кабинет на сайте «Оплатить онлайн» | Redirect `confirmation_url` (без QR в чат) |

Предусловие для MAX: у клиента заполнен `clients.max_user_id` (диалог с ботом).

## Код

| Функция | Файл |
|---|---|
| Счёт / reuse URL | `ensure_yookassa_pay_url` → `src/sfrfr/services/pay_link.py` |
| Оркестратор | `issue_and_deliver_pay_link` |
| Отправка в MAX | `send_pay_link_max` |
| Авто после draft | `maybe_auto_send_pay_link_after_draft` ← `finance_automation` |
| Staff API | `admin_order_pay_link` / `admin_order_remind` |

## Флаги

```env
MAX_PAY_LINK_AUTO_SEND=0   # prod: 0; staging: 1 только при готовом MAX+ЮKassa
CASE_CHAT_PAY_LINK_ENABLED=1   # pay-link из чата бота при готовом счёте (default on)
```

Default **off** для MAX auto: сотрудник жмёт «В MAX». Чат-бот: **on** — при вопросе об оплате.

## Метрики (Prometheus + Метрика)

| Метрика / цель | Назначение |
|---|---|
| `chat_payment_nudge_total{channel,source}` | Бот/staff предложил оплату |
| `chat_payment_nudge_converted_total{channel,source}` | Оплата после нуджа |
| `chat_payment_nudge` / `chat_payment_nudge_paid` | Цели Яндекс Метрики (`scripts/yandex_metrika_ensure_counter.py`) |

Таблица БД: `case_payment_nudges` (миграция `20260902160000_case_payment_nudges.sql`).

## Ограничения

- Не обещать перерасчёт / сумму пенсии в тексте оплаты.
- Не логировать полный `pay_url` и ПДн — только `order_id`/`case_id` prefix + `kind`.
- Двойная оплата: webhook идемпотентен (`apply_provider_payment`).

См. также: `docs/yookassa-setup.md`, `docs/ops/staff-finance-invoices.md`.
