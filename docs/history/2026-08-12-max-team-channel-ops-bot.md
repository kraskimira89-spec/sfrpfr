# 2026-08-12: Канал команды + ops-бот в канале

## Сделано
- В канал **«Проверка стажа — команда»** (`@id8905998693_biz`) добавлен бот **«Проверка стажа-Ops»** (`@id8905998693_3_bot`).
- `chat_id` получен через `GET /chats` токеном ops: **`-77768587291288`**.
- Локально: `MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288`.
- Опубликована и **закреплена** памятка в канале (pin в канале работает).
- Имя бота в коде/доках синхронизировано: **«Проверка стажа-Ops»**.
- `handle_ops_update` обрабатывает `bot_added` / `bot_removed` → `remember_chat_id`.

## VPS
- Прописать `MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288` в `/opt/sfrfr/.env`.
- Убедиться: `MAX_OPS_BOT_TOKEN`, `sfrfr max-ops-webhook-set`, health `ops_bot_configured: yes`.
