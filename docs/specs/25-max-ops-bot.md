# ТЗ-25: Ops-бот MAX (служебный контур)

**Статус:** к реализации / частично в коде  
**Дата:** 2026-08-11  
**Связано:** [ТЗ-20](20-max-private-chat-funnel.md), [ТЗ-23](23-max-channel-promotion.md), [ТЗ-24](24-max-client-boundaries-home.md), [ТЗ-12](12-amocrm.md)

## 1. Проблема

Один бот MAX обслуживает и клиентов, и служебные уведомления (новый лид, вызов специалиста, approve входа staff).  
Если владелец тестирует клиентский сценарий тем же аккаунтом MAX, в одном диалоге смешиваются роли — путаница.

## 2. Цель

Разделить контуры:

| Контур | Бот | Кто открывает | Что происходит |
|--------|-----|---------------|----------------|
| Клиентский | текущий `MAX_BOT_TOKEN` / `MAX_CHAT_URL` | клиенты | диагностика, /login, CTA в кабинет |
| Служебный (Ops) | новый `MAX_OPS_BOT_TOKEN` / `MAX_OPS_CHAT_URL` | админ, операторы, эксперты | лиды, approve staff, вызов к диалогу, ссылки admin/amo |
| Канал | тот же клиентский бот как админ канала | подписчики | посты без ПДн (ТЗ-23) |

Клиент по-прежнему общается в **личном чате клиентского бота**. Специалист отвечает клиенту **в том же клиентском диалоге** (как в ТЗ-24). Ops-бот — только внутренние извещения и кнопки.

## 3. Переменные окружения

```text
MAX_OPS_BOT_TOKEN=          # токен второго бота; пусто = fallback на клиентский (совместимость)
MAX_OPS_WEBHOOK_SECRET=     # опционально, отдельно от MAX_WEBHOOK_SECRET
MAX_OPS_CHAT_URL=           # ссылка «открыть ops-бота» для сотрудников (не на сайт)
```

Цели уведомлений без изменений:

```text
STAFF_LOGIN_APPROVER_MAX_USER_IDS=
STAFF_LOGIN_APPROVER_MAX_CHAT_IDS=   # предпочтительно chat_id группы операторов
```

## 4. API

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/api/integrations/max/webhook` | клиентский бот (как сейчас) |
| POST | `/api/integrations/max/ops/webhook` | ops-бот |
| GET | `/api/integrations/max/health` | оба контура: `bot_configured`, `ops_bot_configured` |

## 5. Поведение кода

1. `get_ops_bot()` → `MaxBotClient(token=MAX_OPS_BOT_TOKEN)` если задан, иначе клиентский токен.  
2. Уведомления о лиде и approve staff **всегда** через `get_ops_bot()`.  
3. Сообщения клиенту (OTP, intake, кабинет) — только клиентский `MaxBotClient()`.  
4. `handle_ops_update`:  
   - `/start` — краткое меню ops (ссылки admin, amo playbook, «уведомления здесь»);  
   - callback approve staff — как сейчас `_approve_staff_by_manager`;  
   - клиентский intake /login — не обрабатывать (подсказка открыть клиентский бот).  

## 6. Ручная настройка в MAX

1. Создать второго бота в кабинете MAX для платформы.  
2. Получить токен → `MAX_OPS_BOT_TOKEN` на VPS.  
3. Зарегистрировать webhook:  
   `sfrfr max-ops-webhook-set` → `…/api/integrations/max/ops/webhook`.  
4. Сотрудники нажимают «Начать» у ops-бота; их `max_user_id` уже в `STAFF_LOGIN_APPROVER_*` / `staff_roles`.  
5. Опционально: создать группу операторов, добавить ops-бота, прописать `STAFF_LOGIN_APPROVER_MAX_CHAT_IDS`.

## 7. Что не делать

- Не публиковать `MAX_OPS_CHAT_URL` на сайте и в рекламе.  
- Не принимать документы в ops-боте.  
- Не смешивать токены: канал постов остаётся на клиентском боте (админ канала).  
- Не обещать клиенту «отдельный чат администратора» на витрине (ТЗ-24).

## 8. Критерии готовности

1. При заданном `MAX_OPS_BOT_TOKEN` лид и approve staff не пишут в клиентский диалог владельца-тестера.  
2. Клиентский `/start` без изменений для клиента.  
3. Без ops-токена поведение = текущее (fallback).  
4. Ops `/start` отвечает служебным текстом.  
5. Документация: этот ТЗ + `docs/ops/max-ops-bot-setup.md`.

## 9. Файлы

- `src/sfrfr/core/config.py` — новые поля  
- `src/sfrfr/integrations/max/client.py` — фабрика  
- `src/sfrfr/integrations/max/ops_bot.py` — `get_ops_bot`, `handle_ops_update`  
- `src/sfrfr/api/routes/max_webhook.py` — `/ops/webhook`  
- `src/sfrfr/api/routes/public_leads.py` — notify через ops  
- `src/sfrfr/integrations/max/handler.py` — staff notify через ops  
- `.env.example`, CLI webhook-set  
