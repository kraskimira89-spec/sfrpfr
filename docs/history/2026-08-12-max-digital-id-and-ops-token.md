# 2026-08-12: Digital ID research + ops-бот «Проверка стажа-Ops»

## Сделано
- Добавлен `docs/marketing-sales/research-max-digital-id-for-sfrfr.md` (API age-verification, границы кабинет ≠ чат).
- Обновлён индекс `docs/marketing-sales/README.md`.
- Канон ТЗ-25 и ops-setup: имя бота **«Проверка стажа-Ops»** (`id8905998693_3_bot`), env `MAX_OPS_BOT_TOKEN` / `MAX_OPS_CHAT_URL`.

## Проверка токена бота для специалистов
- Рабочий токен бота специалистов должен жить только в `MAX_OPS_BOT_TOKEN` (не в `MAX_BOT_SPECIALISTS_*`).
- `MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot`.
- Канал команды: **«Проверка стажа — команда»** `@id8905998693_biz` → https://max.ru/id8905998693_biz  
  Env: `MAX_SPECIALISTS_CHANNEL_URL` / `MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288`.

## Следующий шаг на VPS
- Прописать `MAX_OPS_BOT_TOKEN` + `MAX_OPS_CHAT_URL` + `MAX_SPECIALISTS_CHANNEL_CHAT_ID`, `sfrfr max-ops-webhook-set`, перезапуск API.
- Health: `ops_bot_configured: yes`.
