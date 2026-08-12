# 2026-08-12: Digital ID research + проверка ops/specialists MAX

## Сделано
- Добавлен `docs/marketing-sales/research-max-digital-id-for-sfrfr.md` (API age-verification, границы кабинет ≠ чат).
- Обновлён индекс `docs/marketing-sales/README.md`.

## Проверка токена бота для специалистов
- В `.env` есть рабочий токен под именем `MAX_BOT_SPECIALISTS_STAFF_LOGIN_APPROVER_TOKEN` (бот `id8905998693_3_bot`, `/me` = 200).
- Канон ТЗ-25 ждёт `MAX_OPS_BOT_TOKEN` — переменная **пуста** локально и на prod (`ops_bot_configured: no`).
- Код **не читает** `MAX_BOT_SPECIALISTS_*`; webhook у specialists-бота пустой.
- Клиентский бот отдельно: `id8905998693_1_bot`; токены разные.

## Следующий шаг (по запросу)
- Прописать алиас/переименовать в `MAX_OPS_BOT_TOKEN` + `MAX_OPS_CHAT_URL`, выставить ops webhook, перезапуск API.
