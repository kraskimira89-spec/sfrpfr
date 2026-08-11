# Ops-бот MAX: настройка

Служебный бот для админов и специалистов. Клиентский бот не трогаем.

Подробности: [ТЗ-25](../specs/25-max-ops-bot.md).

## Зачем

Чтобы уведомления (лид, approve входа staff) не приходили в тот же чат, где вы тестируете клиентский сценарий.

## Шаги

1. В кабинете платформы MAX создайте **второго** бота (например «Проверка стажа — Ops»).
2. Скопируйте токен в `/opt/sfrfr/.env`:

```bash
MAX_OPS_BOT_TOKEN=...
MAX_OPS_WEBHOOK_SECRET=...   # желательно отдельный секрет
MAX_OPS_CHAT_URL=https://max.ru/<id_ops_bot>
```

3. Перезапустите API.
4. Зарегистрируйте webhook:

```bash
cd /opt/sfrfr && .venv/bin/sfrfr max-ops-webhook-set
# → https://api.proverkastaza.ru/api/integrations/max/ops/webhook
```

5. Откройте ops-бота с аккаунта руководителя → «Начать».
6. Убедитесь, что `STAFF_LOGIN_APPROVER_MAX_USER_IDS` содержит ваш MAX user_id (или используйте группу + `STAFF_LOGIN_APPROVER_MAX_CHAT_IDS`).

## Проверка

1. Тестовая заявка с сайта → сообщение в **ops**-диалоге / группе, не в клиентском боте.  
2. Клиентский бот: `/start` — диагностика как раньше.  
3. `GET /api/integrations/max/health` → `ops_bot_configured: yes`.

## Пока токена нет

Код делает fallback на клиентский бот — поведение как до ТЗ-25.
