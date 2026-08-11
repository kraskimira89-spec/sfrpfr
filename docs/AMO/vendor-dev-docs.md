# amoCRM — документация для разработчиков (оглавление)

Источник: [developers](https://www.amocrm.ru/developers/) · [API Reference](https://www.amocrm.ru/developers/content/crm_platform/api-reference) · срез: 2026-07-27  
Формат: **ссылка · раздел · кратко · зачем SFRFR**.

Код проекта: `src/sfrfr/integrations/amocrm/` · ТЗ: `docs/specs/12-amocrm.md` · setup: `docs/ops/amocrm-setup.md`.

---

## Навигация платформы разработчика

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [API Reference (индекс)](https://www.amocrm.ru/developers/content/crm_platform/api-reference) | Карта методов v4 | Таблица всех entity API | **P0** — точка входа |
| [Предметная область](https://www.amocrm.ru/developers/content/crm_platform/subject_area) | Модель данных | Сделка, контакт, поля, webhook, источники | **P0** — ментальная модель |
| [Changelog](https://www.amocrm.ru/developers/content/changelog) | Changelog | Изменения API | P1 — перед апгрейдом |
| [Начало интеграций](https://www.amocrm.ru/developers/content/integrations/intro) | Виды интеграций | Приватная / публичная / внешняя / отраслевая | **P0** — у нас **приватная** + long-lived token |

---

## OAuth и доступ

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [oAuth 2.0](https://www.amocrm.ru/developers/content/oauth/oauth) | Протокол | Roles, code, access/refresh | **P0** |
| [OAuth по шагам](https://www.amocrm.ru/developers/content/oauth/step-by-step) | Практика | Создание интеграции, ключи, токены | **P0** — уже в amocrm-setup |
| [Кнопка на сайт](https://www.amocrm.ru/developers/content/oauth/button) | External button | OAuth из кнопки на лендинге | P2 — не наш путь (у нас server token) |
| [Параметры аккаунта](https://www.amocrm.ru/developers/content/crm_platform/account-info) | Account | GET свойств аккаунта / справочники | P1 — диагностика |

---

## CRM Platform API — ядро для SFRFR

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Сделки (leads)](https://www.amocrm.ru/developers/content/crm_platform/leads-api) | Leads | list/get/POST/PATCH, **complex** lead+contact | **P0** — `sync_case_to_amocrm` |
| [Неразобранное](https://www.amocrm.ru/developers/content/crm_platform/unsorted-api) | Unsorted | accept/decline/link входящих | P1 — если подключим источники amo |
| [Воронки и этапы](https://www.amocrm.ru/developers/content/crm_platform/leads_pipelines) | Pipelines/statuses | CRUD воронок и статусов | **P0** — `AMO_PIPELINE_ID` / `AMO_STATUS_ID` |
| [Альфа-фильтрация](https://www.amocrm.ru/developers/content/crm_platform/filters-api) | Filters | Фильтры списков | P1 — поиск сделки по CASE_ID |
| [Контакты](https://www.amocrm.ru/developers/content/crm_platform/contacts-api) | Contacts | CRUD контактов | **P0** — телефон/email без лишних ПДн |
| [Компании](https://www.amocrm.ru/developers/content/crm_platform/companies-api) | Companies | CRUD компаний | P2 — B2C обычно без компании |
| [Связи сущностей](https://www.amocrm.ru/developers/content/crm_platform/entity-links-api) | Links | link/unlink lead↔contact | **P0** — если не complex |
| [Поля и группы](https://www.amocrm.ru/developers/content/crm_platform/custom-fields) | Custom fields | типы, create, примеры значений | **P0** — `amocrm-ensure-fields` |
| [Теги](https://www.amocrm.ru/developers/content/crm_platform/tags-api) | Tags | теги сущностей | **P1** — CHANNEL/SOURCE |
| [Задачи](https://www.amocrm.ru/developers/content/crm_platform/tasks-api) | Tasks | создать/закрыть задачу | **P1** — пинг оператору на лид |
| [События и примечания](https://www.amocrm.ru/developers/content/crm_platform/events-and-notes) | Notes/events | timeline, notes | **P1** — служебные заметки без ПДн |
| [Пользователи и роли](https://www.amocrm.ru/developers/content/crm_platform/users-api) | Users/roles | список юзеров, роли | P1 — назначение ответственного |
| [Источники](https://www.amocrm.ru/developers/content/crm_platform/sources-api) | Sources | источники лидов | **P1** — веб / MAX |
| [Списки / каталоги](https://www.amocrm.ru/developers/content/crm_platform/catalogs-api) | Catalogs | товары, элементы | P2 |
| [Товары](https://www.amocrm.ru/developers/content/crm_platform/products-api) | Products | список товаров | P2 |
| [Покупатели](https://www.amocrm.ru/developers/content/crm_platform/customers-api) | Customers | покупатели + транзакции | P2 — success fee |
| [Статусы/сегменты покупателей](https://www.amocrm.ru/developers/content/crm_platform/customers-statuses-api) | Customer statuses | сегментация | P2 |

---

## Webhooks, боты, виджеты

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Вебхуки API](https://www.amocrm.ru/developers/content/crm_platform/webhooks-api) | Webhooks CRUD | подписка destination + settings | **P1** — lead status → SFRFR |
| [Формат webhook](https://www.amocrm.ru/developers/content/crm_platform/webhooks-format) | Payload | form-urlencoded entity/action | **P1** — парсер на FastAPI |
| [DP: Webhooks](https://www.amocrm.ru/developers/content/digital_pipeline/webhooks) | Digital Pipeline hooks | триггер «отправить webhook» | **P1** — проще UI, чем полный webhook API |
| [Salesbot API](https://www.amocrm.ru/developers/content/crm_platform/salesbot-api) | Salesbot | запуск/управление ботом | P2 |
| [Виджеты API](https://www.amocrm.ru/developers/content/crm_platform/widgets-api) | Widgets | install/list виджетов | P2 — UI в карточке сделки |
| [JS-виджет / manifest](https://www.amocrm.ru/developers/content/integrations/script_js) | Widget SDK | области вставки, script.js | P2 — кнопка «открыть дело SFRFR» в карточке |
| [Требования к публичным](https://www.amocrm.ru/developers/content/integrations/requirements) | Модерация | правила marketplace | P2 — нам не нужно (приватная) |

---

## Чаты, файлы, телефония, нотификации

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [API чатов (хаб)](https://www.amocrm.ru/developers/content/chats/chat) | Chats API | канал сообщений в amo | **P1** — если сведём MAX↔amo inbox |
| [Шаблоны чатов](https://www.amocrm.ru/developers/content/crm_platform/chat-templates-api) | Chat templates | шаблоны ответов | P2 |
| [Беседы](https://www.amocrm.ru/developers/content/crm_platform/talks-api) | Talks | получить/закрыть беседу | P1 |
| [API файлов](https://www.amocrm.ru/developers/content/files/files-capabilities) | Files | upload/attach | **Не для сканов** (ТЗ-12) |
| [Добавление звонков](https://www.amocrm.ru/developers/content/crm_platform/calls-api) | Calls | логирование звонков | P2 |
| [Короткие ссылки](https://www.amocrm.ru/developers/content/crm_platform/short_links) | Short links | создание short URL | P2 |
| [Подписчики сущности](https://www.amocrm.ru/developers/content/crm_platform/subscriptions-api) | Subscriptions | кто следит за сделкой | P2 |
| [Центр нотификаций](https://www.amocrm.ru/developers/content/notifications/api) | Notifications API | push в UI amo | P2 · обзор: [center](https://www.amocrm.ru/developers/content/notifications/center) |
| [API телефонии](https://www.amocrm.ru/developers/content/telephony/api) | Telephony | CTI-интеграции | P2 |

---

## Официальный PHP SDK (справочно)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [amocrm-api-php](https://github.com/amocrm/amocrm-api-php) | PHP client | OAuth + сервисы leads/contacts/… | P2 — у нас Python; полезно как эталон методов |

---

## Карта усиления SFRFR (что брать из каких разделов)

| Цель в проекте | Читать в первую очередь |
|----------------|-------------------------|
| Создать/обновить сделку + контакт с CASE_ID | leads-api · custom-fields · contacts-api · OAuth step-by-step |
| Узнать / сменить этап воронки | leads_pipelines · leads PATCH status_id |
| Найти сделку по CASE_ID | filters-api · leads list filter custom_fields |
| Этап в amo → обновить дело в Supabase | webhooks-api + webhooks-format **или** DP webhooks |
| Задача менеджеру на новый лид | tasks-api |
| Кнопка «открыть кабинет SFRFR» в карточке | integrations/intro · script_js · widgets-api |
| MAX-сообщения в amo | support MAX + chats API (продуктово решить: один бот или два контура) |
| Не тащить ИЛС/сканы | files — **исключить**; notes — только метаданные |

---

## Уже закрыто у нас (не дублировать из доки вслепую)

| Тема | Статус в SFRFR |
|------|----------------|
| Приватная интеграция + long token | `docs/ops/amocrm-setup.md` |
| leads complex + custom fields | `src/sfrfr/integrations/amocrm/` |
| Запрет файлов/СНИЛС в amo | ТЗ-12 |
| Публичный лид → amo | `public_leads` + QA `lead-amocrm-e2e.md` |

### Логичные следующие усиления по доке

1. **Webhook status** → sync этапа обратно в SFRFR.  
2. **Task on lead create** → оператор видит задачу.  
3. **Widget / note** со ссылкой `cabinet` / admin case.  
4. Осознанное решение по **MAX↔amo** (источник в amo vs наш Bot API).
