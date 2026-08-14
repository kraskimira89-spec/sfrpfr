# Ops-бот MAX: настройка

Служебный бот **«Проверка стажа-Ops»** (`id8905998693_3_bot`) для админов и специалистов.  
Клиентский бот **«Стаж и пенсия»** (`id8905998693_1_bot`) не трогаем.

Канон: [ТЗ-25](../specs/25-max-ops-bot.md).

## Зачем

Чтобы уведомления (лид, approve входа staff) не приходили в тот же чат, где вы тестируете клиентский сценарий.

## Шаги

1. В кабинете платформы MAX откройте бота **«Проверка стажа-Ops»** (`id8905998693_3_bot`).
2. Скопируйте токен в `/opt/sfrfr/.env` (и локальный `.env`) **только** в канонические имена:

```bash
# ТЗ-25 — ops-бот «Проверка стажа-Ops»
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

## Канал команды

Черновики постов клиентского канала приходят сюда с кнопками **Опубликовать** / **Редактировать**.
Подробно: [max-channel-review.md](./max-channel-review.md).

| | |
|---|---|
| Название | **Проверка стажа — команда** |
| Ник | `@id8905998693_biz` |
| URL | https://max.ru/id8905998693_biz |
| Env | `MAX_SPECIALISTS_CHANNEL_URL`, `MAX_SPECIALISTS_CHANNEL_CHAT_ID` |
| chat_id | `-77768587291288` (зафиксирован 2026-08-12; ops-бот добавлен в канал) |

Это внутренний **канал**, не замена ops-бота. На сайт и в рекламу не публиковать.

### Получить / обновить `chat_id`

1. Добавить бота **«Проверка стажа-Ops»** админом канала (право публиковать).
2. Предпочтительно: `GET /chats` токеном ops-бота → канал с `link` на `id8905998693_biz`.
3. Запасной путь: ops-webhook (`sfrfr max-ops-webhook-set`) + событие `bot_added` (если бот уже был в канале — удалить и добавить снова).
4. Прописать `MAX_SPECIALISTS_CHANNEL_CHAT_ID` на VPS и локально.
5. Публиковать и **закреплять** инструкцию через API (`pin_message` в канале работает; в личном диалоге — нет).

## AI-помощник (ТЗ-27)

В личке ops-бота можно задать вопрос текстом. В канале команды: `@id8905998693_3_bot …` или `/ask …`.

```bash
MAX_OPS_LLM_ENABLED=1
MAX_OPS_LLM_MAX_CHARS=3500
MAX_OPS_LLM_MODEL=deepseek-v4-flash   # Yandex AI Studio DeepSeek
```

Нужны `YANDEX_API_KEY` + `YANDEX_FOLDER_ID`. Health: `ops_llm_enabled: yes`, `ops_llm_model: deepseek-v4-flash`.

## Проверка

1. Тестовая заявка с сайта → сообщение в **канале команды** (если задан `MAX_SPECIALISTS_CHANNEL_CHAT_ID`) и/или в DM руководителей.  
2. Клиентский бот: `/start` — диагностика как раньше.  
3. `GET /api/integrations/max/health` → `ops_bot_configured: yes`, `specialists_channel_configured: yes`.

## Чеклист VPS

На сервере `/opt/sfrfr/.env` (значения токена не коммитить):

```bash
MAX_OPS_BOT_TOKEN=...
MAX_OPS_WEBHOOK_SECRET=...          # опционально
MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot
MAX_SPECIALISTS_CHANNEL_URL=https://max.ru/id8905998693_biz
MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288
# плюс уже существующие STAFF_LOGIN_APPROVER_MAX_USER_IDS / _CHAT_IDS
```

Команды:

```bash
cd /opt/sfrfr
# после правок .env
systemctl restart sfrfr-api   # или ваш unit / compose restart
.venv/bin/sfrfr max-ops-webhook-set
curl -sS https://api.proverkastaza.ru/api/integrations/max/health
# ожидаем: ops_bot_configured=yes, specialists_channel_configured=yes
```

Проверка: отправить тестовую заявку с сайта → пост в канале **«Проверка стажа — команда»**.

## Пока токена нет

Код делает fallback на клиентский бот — поведение как до ТЗ-25.
