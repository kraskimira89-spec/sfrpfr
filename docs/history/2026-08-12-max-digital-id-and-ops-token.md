# 2026-08-12: Digital ID research + ops-бот «Проверка стажа спец»

## Сделано
- Добавлен `docs/marketing-sales/research-max-digital-id-for-sfrfr.md` (API age-verification, границы кабинет ≠ чат).
- Обновлён индекс `docs/marketing-sales/README.md`.
- Канон ТЗ-25 и ops-setup приведены к имени бота **«Проверка стажа спец»** (`id8905998693_3_bot`) и env `MAX_OPS_BOT_TOKEN` / `MAX_OPS_CHAT_URL`.

## Проверка токена бота для специалистов
- Рабочий токен бота специалистов должен жить только в `MAX_OPS_BOT_TOKEN` (не в `MAX_BOT_SPECIALISTS_*`).
- `MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot`.
- Канал команды: **«Проверка стажа — команда»** `@id8905998693_biz` → https://max.ru/id8905998693_biz  
  Env: `MAX_SPECIALISTS_CHANNEL_URL` / `MAX_SPECIALISTS_CHANNEL_CHAT_ID` (chat_id — после `bot_added`).

## Следующий шаг на VPS
- Прописать `MAX_OPS_BOT_TOKEN` + `MAX_OPS_CHAT_URL`, `sfrfr max-ops-webhook-set`, перезапуск API.
- Health: `ops_bot_configured: yes`.
