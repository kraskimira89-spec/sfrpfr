# ТЗ-14: Яндекс Workspace (ID / сервисы аккаунта)

**Статус:** проектирование  
**Рабочий аккаунт:** `proverkastaza@yandex.ru`  
**Связано:** [06-integrations-and-security.md](06-integrations-and-security.md), [04-admin-cabinet.md](04-admin-cabinet.md), [12-amocrm.md](12-amocrm.md), [13-document-ingest-v2.md](13-document-ingest-v2.md)  
**Пошаговая настройка OAuth:** ➜ **[../ops/yandex-workspace-setup.md](../ops/yandex-workspace-setup.md)**

Официальные доки:

- [OAuth Яндекс ID](https://yandex.ru/dev/id/doc/ru/)
- [Регистрация приложения для API](https://yandex.ru/dev/id/doc/ru/register-api)
- [Яндекс Диск API](https://yandex.ru/dev/disk/doc/ru/)
- [Телемост API (доступ)](https://yandex.ru/dev/telemost/doc/ru/access)
- [Яндекс 360 API](https://yandex.ru/dev/api360/doc/ru/) (организация / бизнес)

---

## 1. Цель

Подключить к SFRFR **сервисы аккаунта Яндекса** (почта, календарь, Телемост, опционально Диск/контакты) под рабочим ящиком `proverkastaza@yandex.ru`, чтобы сотрудники могли:

- писать клиентам с фирменного адреса;
- создавать ссылку на консультацию (Телемост);
- ставить слоты в календаре;
- (опционально) складывать **не-ПДн** операционные файлы на Диск.

Это **не** замена:

| Уже есть | Остаётся источником истины |
|----------|----------------------------|
| Supabase Storage | сканы ИЛС / трудовой / ПДн |
| amoCRM | воронка и контакты лида |
| MAX | основной клиентский канал |
| Yandex Cloud AI Studio | GPT / Vision (другой контур, API-ключ folder) |
| Google Drive / Calendar | операционка до миграции (если решите не дублировать) |

---

## 2. Два контура «Яндекса» (обязательно различать)

| Контур | Где | Учётные данные | ТЗ |
|--------|-----|----------------|-----|
| **Yandex Cloud / AI Studio** | cloud.yandex.ru | API-ключ, `folder_id` | LLM, Vision (ТЗ-06, ТЗ-13) |
| **Яндекс ID + сервисы** | oauth.yandex.ru + API сервисов | OAuth app + token аккаунта `proverkastaza@…` | **это ТЗ-14** |

Ключ AI Studio **не** даёт доступ к почте/Диску/Телемосту.

---

## 3. Принципы

1. Один служебный аккаунт `proverkastaza@yandex.ru` (или ящик организации 360) — токены только на сервере.
2. **Минимум scopes** — только то, что реально используем в MVP.
3. **ПДн-сканы не на Яндекс.Диск** — только Supabase Storage (ТЗ-06 / ТЗ-13).
4. Контакты клиентов — Supabase + amoCRM; адресная книга Яндекса **не** источник истины.
5. Письма и встречи — действия сотрудника (или явные шаблоны), с записью в `access_audit`.
6. Секреты — `secrets/yandex-workspace.env` (gitignored) + VPS `.env`; не в WordPress.

---

## 4. Продуктовый scope (что подключаем)

### 4.1. MVP (обязательно спроектировать)

| Сервис | Use-case в SFRFR | API / протокол |
|--------|------------------|----------------|
| **Почта (SMTP исходящая)** | письмо клиенту / «запрос документов» с `proverkastaza@…` | OAuth + `mail:smtp` (или SMTP XOAUTH2) |
| **Телемост** | кнопка в admin: «Создать встречу» → ссылка в карточку дела / amo note | `telemost-api:conferences.create` (+ read) |
| **Календарь** | слот консультации, привязка к `case_id` в описании | `calendar:events.write` / `calendar:all` |

### 4.2. Опционально (фаза 2)

| Сервис | Use-case | Ограничение |
|--------|----------|-------------|
| **Почта IMAP** | читать входящие на ящик поддержки, линковать к делу | только с правилами ПДн; не автосоздавать дело из СНИЛС в письме |
| **Яндекс Диск** | шаблоны заявлений, обезличенные пакеты | **запрет** загружать ИЛС/трудовые/паспорт; папка `SFRFR-ops`; дублирует Google Drive ops |
| **Адресная книга** | редко | не дублировать amoCRM |

### 4.3. Вне scope ТЗ-14

- Логин клиентов через Яндекс ID на кабинете (отдельное ТЗ Auth).
- Замена amoCRM контактами Яндекса.
- «Все сервисы Яндекса» (Трекер, Wiki, Forms) без явной потребности.
- Хранение ПДн-документов на Диске.
- Публичный OAuth для каждого сотрудника (MVP = один shared mailbox token; позже — 360 service apps).

---

## 5. Как получить доступ API (сводка)

Полный клик-гайд: [yandex-workspace-setup.md](../ops/yandex-workspace-setup.md).

1. Войти на [oauth.yandex.ru](https://oauth.yandex.ru/) как `proverkastaza@yandex.ru`.
2. Создать приложение типа **«Для доступа к API»** / API access ([register-api](https://yandex.ru/dev/id/doc/ru/register-api)) — без лимита «3 группы login», подходит для своих данных.
3. Указать **Redirect URI** (callback SFRFR или debug-страница Яндекса для ручного токена).
4. В **Доступ к данным** включить scopes из §6.
5. Получить **ClientID** (+ secret при code flow).
6. Выдать токен на аккаунт (implicit `response_type=token` для простого старта **или** authorization code + refresh).
7. Прописать env на VPS, перезапустить API.
8. Проверить: SMTP test / create Telemost / calendar event.

### 5.1. Яндекс 360

Если нужны корпоративные политики, общий домен, service applications организации — подключить **Яндекс 360 для бизнеса** и следовать [api360 access](https://yandex.ru/dev/api360/doc/ru/).  
Личный `@yandex.ru` достаточен для MVP почты/Диска пользователя; **Телемост API** в доке часто завязан на права 360 — проверить доступность scopes в UI приложения; при отказе — создать встречу вручную и вставлять URL, либо оформить 360.

---

## 6. Scopes (ориентир)

Точный список выбирать в UI oauth.yandex.ru (названия могут уточняться). Рекомендуемый набор MVP:

| Scope | Назначение |
|-------|------------|
| `mail:smtp` | исходящая почта |
| `telemost-api:conferences.create` | создать встречу |
| `telemost-api:conferences.read` | прочитать/проверить |
| `calendar:events.write` | создать событие (или `calendar:all` если гранулярность недоступна) |

Фаза 2 (включать только при реализации):

| Scope | Назначение |
|-------|------------|
| `mail:imap_ro` / `mail:imap_full` | чтение ящика |
| `cloud_api:disk.read` / `cloud_api:disk.write` | Диск |
| `addressbook:all` | контакты (не приоритет) |
| `telemost-api:conferences.update` / `delete` | правки встреч |

Заголовок к API:

```http
Authorization: OAuth <access_token>
```

---

## 7. Env

```text
YANDEX_OAUTH_CLIENT_ID=
YANDEX_OAUTH_CLIENT_SECRET=          # если code flow
YANDEX_OAUTH_ACCESS_TOKEN=           # или путь к secrets file
YANDEX_OAUTH_REFRESH_TOKEN=          # если есть
YANDEX_WORKSPACE_EMAIL=proverkastaza@yandex.ru
YANDEX_TELEMOST_ENABLED=true
YANDEX_MAIL_ENABLED=true
YANDEX_CALENDAR_ENABLED=true
YANDEX_DISK_ENABLED=true             # ops-папка SFRFR-ops; ПДн-сканы всё равно запрещены
```

Не смешивать с `YANDEX_API_KEY` / `YANDEX_FOLDER_ID` (Cloud AI).

Файл: `secrets/yandex-workspace.env` (gitignore).

---

## 8. Целевой модуль в коде

```text
src/sfrfr/integrations/yandex_workspace/
  __init__.py          # фасад
  oauth.py             # refresh / headers
  mail.py              # send_message (SMTP XOAUTH2 или API)
  telemost.py          # create_conference → join_url
  calendar_yandex.py   # create_event(case_id, …)
  disk.py              # опционально; whitelist путей без ПДн
```

CLI (позже):

- `sfrfr yandex-workspace-ping`
- `sfrfr yandex-telemost-create --case-id …`
- `sfrfr yandex-mail-send --to … --template request_docs`

Admin API (ТЗ-04):

- `POST /api/admin/cases/{id}/telemost` → сохранить `meeting_url` в meta дела / audit;
- `POST /api/admin/cases/{id}/email` → шаблон письма, без вложений сканов из Storage по умолчанию.

---

## 9. Роли и HITL

| Роль | Почта | Телемост | Календарь | Диск |
|------|-------|----------|-----------|------|
| Оператор | шаблоны «запросить документы / напомнить» | создать ссылку | предложить слот | нет |
| Эксперт | то же + итог консультации | то же | то же | только шаблоны (если disk on) |
| Админ | настройки токена / scopes | всё | всё | политика enable |

Каждое действие: `access_audit` (`yandex_mail_send`, `yandex_telemost_create`, `yandex_calendar_event`).

В письмо **не** вставлять СНИЛС, OCR, signed Storage URL с долгим TTL.

---

## 10. Связь с другими контурами

```text
Клиент ←→ MAX / кабинет
              ↓
         SFRFR API + Supabase (дело, файлы)
              ↓
         amoCRM (воронка)
              ↓
    Yandex Workspace (почта / Телемост / календарь)  ← ТЗ-14
              ↓
    Yandex Cloud AI (GPT / Vision)                  ← ТЗ-06 / 13
```

При создании Телемоста — опционально комментарий в сделку amo (`CASE_ID` уже есть).

---

## 11. Безопасность

- Токен = полный доступ к ящику: ротация, минимальные scopes, доступ к secrets только admin/ops.
- Refresh token хранить encrypted at rest (или OS permissions 600 на VPS).
- Не логировать тело писем и OAuth token.
- При компрометации: отозвать приложение на oauth.yandex.ru, перевыпустить токен.
- Диск: `YANDEX_DISK_ENABLED=true` только для `disk:/SFRFR-ops`; сканы дел не пишутся на Диск.

---

## 12. Этапы внедрения

| Этап | Содержание |
|------|------------|
| **0** | Ops: зарегистрировать OAuth app, получить token, `secrets/yandex-workspace.env` |
| **A** | Модуль oauth + `telemost.create` + кнопка в admin |
| **B** | Исходящая почта (шаблоны) + audit |
| **C** | Календарь событий по `case_id` |
| **D** | IMAP inbox rules (опционально) |
| **E** | Диск `SFRFR-ops` + dual-write Google Calendar → Яндекс |

MVP ТЗ-14 = **0 + A + B**.

---

## 13. Критерии приёмки

- [ ] В docs описаны два контура Cloud vs ID; env не пересекаются с AI Studio.
- [x] Выполнены шаги [yandex-workspace-setup.md](../ops/yandex-workspace-setup.md) на аккаунте `proverkastaza@yandex.ru` (API-проверки 2026-07-28).
- [ ] Без токена интеграции возвращают `skipped`, дело не ломается.
- [x] С токеном: создаётся встреча Телемост, URL сохраняется и виден в admin (API 201; persist — через CLI/admin).
- [x] Исходящее тестовое письмо уходит с `YANDEX_WORKSPACE_EMAIL`.
- [ ] В payload писем/логов нет СНИЛС / OCR / долгоживущих Storage URL.
- [x] Диск: `YANDEX_DISK_ENABLED=true` только `SFRFR-ops`; сканы дел не пишутся на Диск.
- [ ] Действия пишутся в `access_audit`.
- [ ] Оператор не видит raw OAuth token в UI.
- [x] Календарь: CalDAV create + dual-write с Google (`calendar-create --mirror-yandex`).

---

## 14. Вне scope (повторение)

- Клиентский login через Яндекс.
- Полный клон Google Workspace внутри Яндекса «на всякий случай».
- Автоответчик с юридическими гарантиями повышения пенсии.
