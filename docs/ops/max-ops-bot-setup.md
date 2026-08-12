# Ops-бот MAX: настройка

Служебный бот **«Проверка стажа спец»** (`id8905998693_3_bot`) для админов и специалистов.  
Клиентский бот **«Стаж и пенсия»** (`id8905998693_1_bot`) не трогаем.

Канон: [ТЗ-25](../specs/25-max-ops-bot.md).

## Зачем

Чтобы уведомления (лид, approve входа staff) не приходили в тот же чат, где вы тестируете клиентский сценарий.

## Шаги

1. В кабинете платформы MAX откройте бота **«Проверка стажа спец»** (`id8905998693_3_bot`).
2. Скопируйте токен в `/opt/sfrfr/.env` (и локальный `.env`) **только** в канонические имена:

```bash
# ТЗ-25 — ops-бот «Проверка стажа спец»
MAX_OPS_BOT_TOKEN=...
MAX_OPS_WEBHOOK_SECRET=...   # желательно отдельный секрет
MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot
```

Не оставлять токен под устаревшими именами вроде `MAX_BOT_SPECIALISTS_STAFF_LOGIN_APPROVER_TOKEN` — код их **не читает**.

3. Перезапустите API.
4. Зарегистрируйте webhook:

```bash
cd /opt/sfrfr && .venv/bin/sfrfr max-ops-webhook-set
# → https://api.proverkastaza.ru/api/integrations/max/ops/webhook
```

5. Откройте ops-бота с аккаунта руководителя → «Начать».
6. Убедитесь, что `STAFF_LOGIN_APPROVER_MAX_USER_IDS` содержит ваш MAX user_id (или используйте группу + `STAFF_LOGIN_APPROVER_MAX_CHAT_IDS` — это **chat_id**, не username бота).

## Канал специалистов

`https://max.ru/channel_proverkastaza_specialists` — внутренний **канал**, не замена ops-бота.  
Токен канала / chat_id канала не подставлять в `MAX_OPS_BOT_TOKEN`.

## Проверка

1. Тестовая заявка с сайта → сообщение в **ops**-диалоге / группе, не в клиентском боте.  
2. Клиентский бот: `/start` — диагностика как раньше.  
3. `GET /api/integrations/max/health` → `ops_bot_configured: yes`.

## Пока токена нет

Код делает fallback на клиентский бот — поведение как до ТЗ-25.
