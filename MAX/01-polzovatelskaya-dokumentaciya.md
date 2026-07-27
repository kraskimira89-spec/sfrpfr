# MAX — пользовательская / партнёрская документация (оглавление)

Источники: [business.max.ru](https://business.max.ru/) · [dev.max.ru/help](https://dev.max.ru/help) · [help.max.ru](https://help.max.ru/) · срез: 2026-07-27  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Наш бот: «Стаж и пенсия» (`id8905998693_1_bot`) · mini-app: `https://proverkastaza.ru/app/` · чеклист: `docs/ops/cutover-manual-checklist.md`.

---

## Как пользоваться

| Приоритет | Смысл |
|-----------|--------|
| **P0** | Нужно для текущего бота / mini-app / webhook |
| **P1** | Усиление продукта (deeplink, inbox, UX) |
| **P2** | Фоном (каналы, Цифровой ID, end-user help) |

---

## Платформа MAX для партнёров (оператор / админ)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Платформа](https://business.max.ru/) | Кабинет партнёра | Веб-UI: боты, токен, URL mini-app | **P0** — ручные настройки |
| [FAQ: подключение](https://dev.max.ru/help/platform_connection) | Регистрация на платформе | Кто может подключиться, данные, сбои | P1 — онбординг юрлица |
| [FAQ: профиль](https://dev.max.ru/help/organization) | Профиль орг./ИП/самозанятого | Создание и верификация | **P0** — без верификации нет бота |
| [FAQ: чат-боты](https://dev.max.ru/help/chatbots) | Управление ботом | Создание, модерация, ник, токен, удаление, группы | **P0** |
| [FAQ: мини-приложения](https://dev.max.ru/help/miniapps) | Mini-app в UI | URL, кнопка Старт/Открыть, требования https | **P0** — URL `proverkastaza.ru/app/` |
| [FAQ: события](https://dev.max.ru/help/events) | Webhook vs Long Polling | Production = только webhook, HTTPS+доверенный сертификат | **P0** |
| [FAQ: диплинки](https://dev.max.ru/help/deeplinks) | Deep links | `?start=` для бота, `?startapp=` для mini-app, `:share` | **P0** — CTA лендинга |
| [FAQ: интеграция с партнёрами](https://dev.max.ru/help/integration) | CRM / конструкторы | Подключение сторонних сервисов по токену | **P1** — amoCRM↔MAX, не смешивать контуры вслепую |
| [FAQ: каналы](https://dev.max.ru/help/channels) | Каналы бизнеса | Публичные/приватные, лимиты | P2 — новости/блог |
| [FAQ: Цифровой ID](https://dev.max.ru/help/digital-id) | Цифровой ID | Льготы/возраст на кассе | P2 — не ядро SFRFR |
| [FAQ: MAX для бизнеса](https://dev.max.ru/help/miniapp-main) | Mini-app / бот «MAX для бизнеса» | Управление платформой из мессенджера | P1 — админ без ПК |
| [FAQ: поддержка](https://dev.max.ru/help/support) | Поддержка | Как писать о проблеме / идеях | P1 |

---

## Гайды «как сделать» (партнёр, без кода API)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [О платформе](https://dev.max.ru/docs) | Обзор сервисов | Боты, mini-app, каналы, партнёры, Цифровой ID | **P0** — карта продукта |
| [Создание профиля](https://dev.max.ru/docs/maxbusiness/connection) | Подключение | Регистрация + верификация | **P0** |
| [Выбор сервисов](https://dev.max.ru/docs/maxbusiness/selectionservices) | Какие сервисы брать | Боты / mini-app / каналы / ID | P1 |
| [Создание бота](https://dev.max.ru/docs/chatbots/bots-create/create) | Создание на платформе | Карточка бота → модерация → токен | **P0** |
| [Управление ботом](https://dev.max.ru/docs/chatbots/bots-create/manage) | Расширенные настройки | Приватность групп, URL mini-app, кнопка, refresh token | **P0** |
| [Конструктор без кода](https://dev.max.ru/docs/chatbots/bots-nocode) | No-code сценарии | Шаблоны партнёров | P2 — у нас свой FastAPI handler |
| [Подключение mini-app](https://dev.max.ru/docs/webapps/introduction) | Как добавить приложение | URL + кнопка; диплинки `startapp` | **P0** |
| [Создание канала](https://dev.max.ru/docs/channels/create) | Каналы | Публичный/А+/через мессенджер | P2 |
| [Управление каналом](https://dev.max.ru/docs/channels/manage) | Каналы | Права, блокировки | P2 |
| [Интеграция с партнёрами](https://dev.max.ru/docs/partners-integration) | Партнёрские CRM/конструкторы | Токен бота в сторонний сервис | **P1** — vs amo «источник MAX» |
| [Цифровой ID](https://dev.max.ru/docs/digital-id) | Подключение ID | Токен для касс | P2 |

---

## Правила и юр. (для публикации)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Правила размещения](https://dev.max.ru/docs/legal/rules) | Rules | Что можно/нельзя в ботах и mini-app | **P1** — модерация / жалобы |
| [Требования к содержанию](https://dev.max.ru/docs/legal/requirements) | Content requirements | Функциональность приложений | **P1** |
| [Типовое соглашение](https://dev.max.ru/docs/legal/agreement) | User agreement template | Шаблон для разработчика | P2 |
| [Типовая политика ПДн](https://dev.max.ru/docs/legal/privacy) | Privacy template | Политика конфиденциальности | **P1** — сверка с нашими юр.страницами |
| [Changelog платформы](https://dev.max.ru/docs/changelog-platform) | История изменений | Breaking changes UI/правил | P1 |

---

## Help для конечного пользователя мессенджера (клиенты SFRFR)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [О MAX](https://help.max.ru/help/about) | Начало работы | Как пользоваться мессенджером | P2 — FAQ на лендинге |
| [Профиль](https://help.max.ru/help/account) | Аккаунт | Настройки профиля | P2 |
| [Безопасность](https://help.max.ru/help/security) | Security | 2FA, мошенники | **P1** — тексты «как безопасно войти» |
| [Госуслуги](https://help.max.ru/help/gosuslugi) | Госуслуги | Связка с ГУ | P2 |
| [Переписка](https://help.max.ru/help/messages) | Сообщения | Чаты | P2 |
| [Групповые чаты](https://help.max.ru/help/chats) | Группы | Управление чатом | P2 |
| [Каналы](https://help.max.ru/help/channels) | Каналы | Подписка/создание глазами юзера | P2 |
| [Чат-боты (юзер)](https://help.max.ru/help/bots) | Боты для пользователя | Как найти бота, начать диалог, пожаловаться | **P1** — онбординг «откройте бота» |
| [Звонки / контакты / папки](https://help.max.ru/) | Прочее UI | Звонки, контакты, папки | P2 |

---

## Быстрый указатель под задачи SFRFR

| Задача | Смотреть |
|--------|----------|
| Сменить URL mini-app после cutover | FAQ miniapps · Управление ботом |
| Обновить / ротировать `MAX_BOT_TOKEN` | FAQ chatbots · Управление ботом |
| Почему не приходят webhook | FAQ events (+ сертификат Минцифры) |
| CTA «Открыть в MAX» с лендинга | FAQ deeplinks · `?startapp` |
| Текст для пожилых «как начать» | help.max.ru/bots · Безопасность |
| Не дублировать бота в amoCRM вслепую | FAQ integration · partners-integration |
