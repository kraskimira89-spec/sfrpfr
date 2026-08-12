# ТЗ-25: Ops-бот MAX (служебный контур)

**Статус:** в коде / канал команды подключён  
**Дата:** 2026-08-11 (имя бота: «Проверка стажа-Ops», 2026-08-12)  
**Связано:** [ТЗ-20](20-max-private-chat-funnel.md), [ТЗ-23](23-max-channel-promotion.md), [ТЗ-24](24-max-client-boundaries-home.md), [ТЗ-12](12-amocrm.md)  
**Ops:** [../ops/max-ops-bot-setup.md](../ops/max-ops-bot-setup.md)

## 1. Проблема

Один бот MAX обслуживает и клиентов, и служебные уведомления (новый лид, вызов специалиста, approve входа staff).  
Если владелец тестирует клиентский сценарий тем же аккаунтом MAX, в одном диалоге смешиваются роли — путаница.

## 2. Цель

Разделить контуры:

| Контур | Бот (отображаемое имя) | Технический username | Env | Кто открывает | Что происходит |
|--------|------------------------|----------------------|-----|---------------|----------------|
| Клиентский | «Стаж и пенсия» | `id8905998693_1_bot` | `MAX_BOT_TOKEN` / `MAX_CHAT_URL` | клиенты | диагностика, /login, CTA в кабинет |
| Служебный (Ops) | **«Проверка стажа-Ops»** | `id8905998693_3_bot` | `MAX_OPS_BOT_TOKEN` / `MAX_OPS_CHAT_URL` | админ, операторы, эксперты | лиды, approve staff, вызов к диалогу, ссылки admin/amo |
| Канал (публичный) | канал `channel_proverkastaza` | — | `MAX_CHANNEL_URL` | подписчики | посты без ПДн (ТЗ-23); админ канала — клиентский бот |
| Канал специалистов | **«Проверка стажа — команда»** | `@id8905998693_biz` | `MAX_SPECIALISTS_CHANNEL_URL` / `MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288` | сотрудники | внутренний канал; закреп инструкций; **не** ops-токен и не на сайт |


Клиент по-прежнему общается в **личном чате клиентского бота**. Специалист отвечает клиенту **в том же клиентском диалоге** (как в ТЗ-24). Ops-бот — только внутренние извещения и кнопки.

## 3. Переменные окружения

**Канон (читается кодом):**

```text
MAX_OPS_BOT_TOKEN=          # токен бота «Проверка стажа-Ops» (id8905998693_3_bot)
MAX_OPS_WEBHOOK_SECRET=     # опционально, отдельно от MAX_WEBHOOK_SECRET
MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot
MAX_SPECIALISTS_CHANNEL_URL=https://max.ru/id8905998693_biz
MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288
```

Пустой `MAX_OPS_BOT_TOKEN` → fallback на клиентский токен (совместимость до настройки).

**Не канон (не читать в коде):** имена вроде `MAX_BOT_SPECIALISTS_STAFF_LOGIN_APPROVER_TOKEN` — устаревшие ярлыки в локальных `.env`. Значение токена переносить в `MAX_OPS_BOT_TOKEN`, ссылку бота — в `MAX_OPS_CHAT_URL`.

Цели уведомлений без изменений:

```text
STAFF_LOGIN_APPROVER_MAX_USER_IDS=
STAFF_LOGIN_APPROVER_MAX_CHAT_IDS=   # предпочтительно chat_id группы операторов (не username бота)
```

## 4. API

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/api/integrations/max/webhook` | клиентский бот (как сейчас) |
| POST | `/api/integrations/max/ops/webhook` | ops-бот «Проверка стажа-Ops» |
| GET | `/api/integrations/max/health` | `bot_configured`, `ops_bot_configured`, `specialists_channel_configured` |

## 5. Поведение кода

1. `get_ops_bot()` → `MaxBotClient(token=MAX_OPS_BOT_TOKEN)` если задан, иначе клиентский токен.  
2. Уведомления о лиде и approve staff **всегда** через `get_ops_bot()`.  
3. Новый лид: дополнительно пост в `MAX_SPECIALISTS_CHANNEL_CHAT_ID` (канал команды), если задан.  
4. Сообщения клиенту (OTP, intake, кабинет) — только клиентский `MaxBotClient()`.  
5. `handle_ops_update`:  
   - `bot_added` / `bot_removed` — `remember_chat_id` для канала команды;  
   - `/start` — краткое меню ops (ссылки admin, «уведомления здесь»);  
   - callback approve staff — как сейчас `_approve_staff_by_manager`;  
   - клиентский intake /login — не обрабатывать (подсказка открыть клиентский бот).  

## 6. Ручная настройка в MAX

1. Бот для специалистов: отображаемое имя **«Проверка стажа-Ops»**, username **`id8905998693_3_bot`**.  
2. Токен этого бота → `MAX_OPS_BOT_TOKEN` на VPS (и локально).  
3. `MAX_OPS_CHAT_URL=https://max.ru/id8905998693_3_bot` — только для сотрудников, не на сайт.  
4. Зарегистрировать webhook:  
   `sfrfr max-ops-webhook-set` → `…/api/integrations/max/ops/webhook`.  
5. Сотрудники нажимают «Начать» у ops-бота; их `max_user_id` уже в `STAFF_LOGIN_APPROVER_*` / `staff_roles`.  
6. Канал команды: ops-бот админом; `MAX_SPECIALISTS_CHANNEL_CHAT_ID=-77768587291288`.  
7. Опционально: создать группу операторов, добавить ops-бота, прописать `STAFF_LOGIN_APPROVER_MAX_CHAT_IDS`.

## 7. Что не делать

- Не публиковать `MAX_OPS_CHAT_URL` на сайте и в рекламе.  
- Не принимать документы в ops-боте.  
- Не смешивать токены: канал постов остаётся на клиентском боте (админ канала).  
- Не путать **канал команды** ([Проверка стажа — команда](https://max.ru/id8905998693_biz), `@id8905998693_biz`) с **ops-ботом** (`id8905998693_3_bot` / «Проверка стажа-Ops»).  
- Не обещать клиенту «отдельный чат администратора» на витрине (ТЗ-24).

## 8. Критерии готовности

1. При заданном `MAX_OPS_BOT_TOKEN` лид и approve staff не пишут в клиентский диалог владельца-тестера.  
2. Клиентский `/start` без изменений для клиента.  
3. Без ops-токена поведение = текущее (fallback).  
4. Ops `/start` отвечает служебным текстом от имени «Проверка стажа-Ops».  
5. Документация: этот ТЗ + `docs/ops/max-ops-bot-setup.md`.  
6. Health: `ops_bot_configured: yes` после выставления канонических env.  
7. В канале команды есть закреплённая памятка; `chat_id` известен.

## 9. Файлы

- `src/sfrfr/core/config.py` — поля `max_ops_*`  
- `src/sfrfr/integrations/max/client.py` — фабрика  
- `src/sfrfr/integrations/max/ops_bot.py` — `get_ops_bot`, `handle_ops_update`  
- `src/sfrfr/api/routes/max_webhook.py` — `/ops/webhook`  
- `src/sfrfr/api/routes/public_leads.py` — notify через ops  
- `src/sfrfr/integrations/max/handler.py` — staff notify через ops  
- `.env.example`, CLI webhook-set  
