# MAX — документация для разработчиков (оглавление)

Источники: [dev.max.ru/docs](https://dev.max.ru/docs) · [API](https://dev.max.ru/docs-api) · [MAX UI](https://dev.max.ru/ui) · срез: 2026-07-27  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Код: `src/sfrfr/integrations/max/` · mini-app: `web/max-miniapp/` · ТЗ-09: `docs/specs/09-client-channels-parity.md` · API base: `platform-api2.max.ru`.

---

## Карта разделов docs

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [О платформе](https://dev.max.ru/docs) | Индекс | Боты, mini-app, каналы, партнёры, ID | **P0** |
| [API Reference / обзор](https://dev.max.ru/docs-api) | HTTP API | Методы, коды, webhook/long poll, клавиатура, кнопки | **P0** |
| [Подготовка к API](https://dev.max.ru/docs/chatbots/bots-coding/prepare) | Кодинг бота | Запросы, токен, уведомления, диплинки `?start=` | **P0** |
| [Библиотека JavaScript](https://dev.max.ru/docs/chatbots/bots-coding/js) | JS SDK | Обёртка над API | P2 — у нас Python |
| [Библиотека Golang](https://dev.max.ru/docs/chatbots/bots-coding/go) | Go SDK | Обёртка над API | P2 |
| [Примеры ботов](https://dev.max.ru/docs/chatbots/bots-coding/examples) | Examples | Готовые сценарии | **P1** — сверить UX `/start` |
| [Mini-app intro](https://dev.max.ru/docs/webapps/introduction) | WebApps | HTTPS URL, кнопка, deeplink `startapp`, share | **P0** |
| [MAX Bridge](https://dev.max.ru/docs/webapps/bridge) | `window.WebApp` | initData, user, chat, start_param, методы UI | **P0** — auth mini-app |
| [Валидация initData](https://dev.max.ru/docs/webapps/validation) | HMAC WebAppData | Проверка подписи на сервере | **P0** — portal MAX auth |
| [MAX UI](https://dev.max.ru/ui) | React-компоненты | Дизайн-система под MAX | **P1** — полировка mini-app |
| [Changelog платформы](https://dev.max.ru/docs/changelog-platform) | Changes | Breaking / релизы | P1 |

---

## API: базовые правила (из docs-api)

| Тема | Суть | Для SFRFR |
|------|------|-----------|
| Host | Только `https://platform-api2.max.ru` (не `platform-api.max.ru`) | **P0** — `MAX_API_BASE` |
| Auth | `Authorization: <token>` (query token **запрещён**) | **P0** |
| Минцифры CA | Доверенные сертификаты для TLS к API и webhook | **P0** — `certs/` + ssl_context |
| RPS | До ~30 rps на API | P1 — rate limits |
| Production updates | Только **Webhook**; Long Polling — не для prod | **P0** |
| Webhook HTTPS | С 25 мая 2026: без HTTP и self-signed; иначе отписка | **P0** |
| GET /chats | С июня 2026 **не поддерживается** → POST /subscriptions | P1 — если код ещё дергает /chats |

---

## API: методы и объекты (ориентир)

Официальный перечень и детали — на [docs-api](https://dev.max.ru/docs-api). Ниже — что брать для усиления SFRFR.

| Метод / тема | Кратко | Для SFRFR |
|--------------|--------|-----------|
| `GET /me` | Инфо о боте (user_id, username, name) | **P0** — health / verify token |
| `PATCH /me` | Описание бота | P2 |
| `PATCH /me/commands` | Команды меню бота | **P1** — `/start` `/help` в меню |
| `POST /subscriptions` | Подписка webhook + URL + secret | **P0** — `sfrfr max-subscribe` |
| `GET /subscriptions` | Список подписок | **P0** — диагностика |
| `GET /updates` | Long Polling | Только dev |
| `POST /messages` | Отправка сообщений + attachments | **P0** — ответы бота, OTP, CTA |
| `GET /messages` / `GET /messages/{id}` | Чтение сообщений | **P1** — контакты / mid для share |
| `PATCH /chats/{chatId}` | Метаданные чата | P2 |
| Inline keyboard | До 210 кнопок / 30 рядов | **P0** |
| Типы кнопок | `callback`, `link`, `open_app`, `request_contact`, `request_geo_location`, `message`, `clipboard` | **P0** — open_app / callback / contact |
| `request_contact` + `hash` | Подтверждение, что номер = аккаунт MAX | **P1** — привязка телефона |
| `open_app` | Открыть mini-app из сообщения | **P0** |
| `message_callback` | Событие нажатия callback | **P0** — «Подтвердить вход в веб» |
| `bot_started` / `bot_added` | Старт / добавление в чат | **P0** — онбординг |
| chat_id | Из Update или `WebApp.initData` | **P0** |

---

## Mini-app / Bridge (детали для портала)

| Ссылка / поле | Кратко | Для SFRFR |
|---------------|--------|-----------|
| [validation](https://dev.max.ru/docs/webapps/validation) | HMAC-SHA256(`WebAppData`, bot_token) → hash | **P0** — не доверять initDataUnsafe на сервере |
| `initData` / `WebAppData` | Подписанная строка запуска | **P0** |
| `initDataUnsafe.user` | id, name, username, language_code, photo | **P0** — `max_user_id` |
| `chat` | id, type DIALOG/CHAT/CHANNEL | P1 |
| `start_param` | Payload из `?startapp=` (до 512, `[A-Za-z0-9_-]`) | **P1** — deep-link case_id |
| TTL auth_date | Обычно ~1 час | **P1** — `MAX_MINIAPP_AUTH_TTL` |
| `openLink` vs `openMaxLink` | Внешний браузер vs шторка MAX | **P1** — ссылки на оферту / кабинет |
| `shareMaxContent` | Шеринг mid в чат | P2 |

---

## Партнёрский no-code / внешние SDK (справочно)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [bots-nocode](https://dev.max.ru/docs/chatbots/bots-nocode) | Конструкторы | Сценарии без своего бэкенда | P2 — конкурирует с нашим handler |
| [partners-integration](https://dev.max.ru/docs/partners-integration) | Партнёры | CRM/чат-платформы по токену | **P1** — граница с amoCRM |

---

## Юр. для разработчика

| Ссылка | Раздел | Для SFRFR |
|--------|--------|-----------|
| [rules](https://dev.max.ru/docs/legal/rules) | Правила размещения | **P1** |
| [requirements](https://dev.max.ru/docs/legal/requirements) | Требования к приложениям | **P1** |
| [agreement](https://dev.max.ru/docs/legal/agreement) · [privacy](https://dev.max.ru/docs/legal/privacy) | Шаблоны | P2 — сверка с WP офертой/ПДн |

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| Webhook стабильный на VPS | docs-api (subscriptions) · help/events · CA Минцифры |
| Auth mini-app → portal | bridge · validation · ТЗ-09 |
| Кнопка «открыть кабинет» / OTP | messages + callback · request_contact |
| Deep-link дело / канал | introduction (startapp) · help/deeplinks · prepare (?start=) |
| Меню команд бота | PATCH /me/commands · examples |
| UI как у MAX | MAX UI · bridge theme methods |
| Не сломать cutover URL | introduction · manage (только UI меняет URL mini-app) |

---

## Уже есть у нас (не дублировать вслепую)

| Тема | Где в SFRFR |
|------|-------------|
| Webhook + handler | `integrations/max` |
| Mini-app статика | `web/max-miniapp` → `/app/` |
| `MAX_API_BASE=platform-api2.max.ru` | `.env` / VPS |
| CA Минцифры | `certs/` + ssl_context |
| Portal / link OTP | `api/routes/portal.py`, cabinet MAX wizard |
| URL mini-app на новом домене | cutover checklist ✅ |

### Логичные следующие шаги по доке

1. Проверить подпись **initData** на всех portal/mini-app входах (validation).  
2. Команды меню бота через `PATCH /me/commands`.  
3. Deep-link `startapp=<case>` в уведомлениях.  
4. Явная политика: **наш Bot API** vs **источник MAX в amoCRM** (не два бота без схемы).
