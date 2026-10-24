# SFRFR-111: сценарий будущего live MAX (не выполнять без разрешения)

**Статус:** подготовлен, **не запущен**.  
Live MAX / реальные оплаты / production — только после отдельного OK владельца.

## Границы

| Параметр | Значение |
|---|---|
| Получатель | выделенный тестовый MAX user (не клиент) |
| Дело | синтетическое, без ПДн реальных людей |
| Оплата | запрещена; `PRECHECK_ORDER_SANDBOX=1` или pay_link off |
| Уведомления | kill-switch / флаг отключения enqueue MAX |

## Сообщения и callback (ожидаемый порядок)

1. Staff: «Проверить документы» → job completed.
2. Клиенту (тест): резюме + кнопки `precheck:summary:<id>`, `precheck:explain:<id>`, …
3. При оффере: `precheck:offer_info:<id>` → состав/цена без заказа.
4. `precheck:order:<id>` → существующий DIAG-маршрут; в live без sandbox — pay link только после подтверждённого create.
5. Повтор `order` → тот же заказ / already_paid / честный fail.
6. `precheck:decline:<id>` → оффер снят.
7. Устаревший check_id → stale, коммерция не применяется.

## Критерии остановки

- Любая реальная платёжная ссылка ЮKassa на нетестовый магазин.
- Сообщение ушло не тестовому user_id.
- Неизвестный исход create_order / orders_load.
- Повтор создал второй DIAG draft.

## Повторы

Проверить: двойной callback order, F5 не влияет (сервер), повтор после decline.

## Отключение

- Выключить worker/notify flag для precheck MAX.
- `MAX_BOT_OWNED_PAY_LINK=0` / sandbox.
- Не слать webhook в prod-бот.

Выполнение — отдельный шаг после browser E2E и зелёного order/sandbox.
