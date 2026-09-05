# 2026-09-05 — MAX: опрос про выписки на Госуслугах

## Цель

Сервисный вопрос клиентам с привязанным MAX (включая закрытые дела): получилось ли заказать выписку ИЛС / о стаже на Госуслугах. Только личный бот, не канал.

## Аудит

- Скрипт: `scripts/max_gosuslugi_survey_outreach.py` (audit / dry-run / apply / verify).
- `case_chat_outbox` на self-host PostgREST: **PGRST205** (таблица не в schema cache) → доставка напрямую через `MaxBotClient` после insert в `case_messages`.
- Кандидаты (дедуп по `max_user_id`, без test): **34**; quiet hours на момент рассылки: нет.

## Результат доставки MAX

| Статус | Кол-во |
|--------|--------|
| sent | 25 |
| failed | 9 |

Ошибки API (без user_id в git): **8× 403 Forbidden**, **1× 404 Not Found** — диалог недоступен боту (блок / удаление / нет чата). Сообщения в `case_messages` у кандидатов есть; повторный blast не делали.

## Ограничения соблюдены

- contact_policy / dedup / без ПДн в отчёте;
- submission-position в тексте;
- не канал `channel_proverkastaza`.

## Владельцу

- Ответы клиентов смотреть в личных чатах дел / кабинете.
- При необходимости: точечный retry только failed (не всем 34).
- Инфра: починить exposure `case_chat_outbox` в PostgREST, когда будет окно.
