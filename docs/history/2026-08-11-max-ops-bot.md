# 2026-08-11 — ТЗ-25 Ops-бот MAX

## Запрос

Отделить служебный чат (админ/специалисты) от клиентского бота: лиды и approve staff не должны смешиваться с клиентской диагностикой.

## Сделано в коде

- ТЗ: `docs/specs/25-max-ops-bot.md`, ops: `docs/ops/max-ops-bot-setup.md`
- Env: `MAX_OPS_BOT_TOKEN`, `MAX_OPS_WEBHOOK_SECRET`, `MAX_OPS_CHAT_URL`
- `get_ops_bot()` / `MaxBotClient.for_ops()` — fallback на клиентский токен
- Webhook `POST /api/integrations/max/ops/webhook` + `handle_ops_update`
- Уведомления о лиде и approve staff → ops-бот
- CLI: `sfrfr max-ops-webhook-set`

## Ручной шаг владельца

1. Создать второго бота в MAX
2. Прописать токен на VPS
3. `sfrfr max-ops-webhook-set`
4. Сотрудники открывают ops-бота → «Начать»
