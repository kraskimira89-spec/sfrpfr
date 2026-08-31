# Настройка Яндекс Workspace (OAuth) для SFRFR

**ТЗ:** [../specs/14-yandex-workspace.md](../specs/14-yandex-workspace.md)  
**Версия гайда:** 1.2 (2026-07-28)

Отдельно от **Yandex Cloud AI Studio** (`YANDEX_API_KEY` / `folder_id`) — здесь только доступ к почте / Телемосту / календарю / Диску (ops).

### Модель доступов (обязательно)

| Что | Кто / какой токен | Env |
|-----|-------------------|-----|
| Диск, Почта, Календарь | **Общая почта организации** `proverkastaza@yandex.ru` | `YANDEX_OAUTH_*` |
| Телемост | **Сотрудник организации** `info@proverkastaza.ru` | `YANDEX_TELEMOST_OAUTH_*` |

Не смешивать: токен общей почты не использовать для Телемоста и наоборот.

---

## Статус выполнения (проверено 2026-07-28)

| Шаг | Статус | Факт |
|-----|--------|------|
| 0. Контур | ✅ | Org-mailbox + employee Telemost; Диск `SFRFR-ops` + зеркало `SFRFR-cases`; dual-write календаря |
| 1. OAuth-приложение | ✅ | `SFRFR Workspace` + `SFRFR_telemost` |
| 2. Scopes | ✅ | Почта / календарь / Диск / Телемост — токены живые |
| 3. OAuth-токены | ✅ | Workspace → `proverkastaza`; Telemost → `info@proverkastaza.ru` |
| 4. Секреты | ✅ | `secrets/yandex-workspace.env` + блок в локальном `.env`; на VPS — сверить вручную |
| 5. Проверки API | ✅ | см. таблицу ниже |
| 6. Ротация | ⬜ | по необходимости |

### Проверки API (2026-07-28, полный healthcheck)

| Проверка | Результат |
|----------|-----------|
| Env: блок Yandex в `.env` | **дописан** (раньше только комментарий; рабочие значения были в secrets) |
| Identities токенов | Workspace=`proverkastaza` ≠ Telemost=`info@proverkastaza.ru` ✅ |
| `login.info` / ping | **ok**, login `proverkastaza` |
| Диск status + `SFRFR-ops` / `SFRFR-cases` | **ok** |
| Календарь create (CalDAV) | **201** |
| Почта SMTP XOAUTH2 | **ok** (письмо на себя) |
| Телемост create (employee) | **201**, `join_url` |
| Dual-write Google↔Яндекс | CLI `calendar-create --mirror-yandex` |

CLI:

```bash
sfrfr yandex-workspace-ping
sfrfr yandex-disk-status
sfrfr yandex-telemost-create -c <uuid>
sfrfr calendar-create -c <uuid> --start 2026-08-01T15:00:00+03:00
sfrfr calendar-mirror-yandex
```

---

## Что понадобится

- Браузер, вход в `proverkastaza@yandex.ru`
- Права менять VPS `.env` / `secrets/`
- Callback URL API (или ручной выпуск токена на первом этапе)

---

## Шаг 0. Решить контур

| Вопрос | Решение SFRFR (2026-07-28) |
|--------|----------------------------|
| Личный ящик `@yandex.ru` или Яндекс 360? | Личный; Телемост API уже отвечает 201 на токене `SFRFR_telemost` |
| Нужен ли Диск? | **Да** (`YANDEX_DISK_ENABLED=true`): `disk:/SFRFR-ops` (ops без ПДн в путях) + зеркало сканов `disk:/SFRFR-cases/{case_id}`. Primary документов — Supabase Storage / local uploads |
| Дублировать Google Calendar? | **Да**, dual-write: Google остаётся основным create-path, Яндекс — зеркало |

---

## Шаг 1. Создать OAuth-приложение

1. Откройте [https://oauth.yandex.ru/](https://oauth.yandex.ru/) под `proverkastaza@yandex.ru`.
2. **Создать новое приложение**.
3. Тип: для **доступа к API** / работы со **своими** данными  
   ([инструкция register-api](https://yandex.ru/dev/id/doc/ru/register-api)).
4. Название: `SFRFR Workspace`.
5. Платформы: **Веб-сервисы**.
6. **Callback URI** (выберите один вариант):
   - Production: `https://api.proverkastaza.ru/api/integrations/yandex/oauth/callback`
   - Пока кода callback нет: можно использовать отладочный redirect из доки Яндекса / `response_type=token` (шаг 3).
7. Сохраните **ClientID** (и **Client secret**, если выдан).

Отдельно создано приложение **`SFRFR_telemost`** (только scopes Телемоста) — токен в `YANDEX_TELEMOST_OAUTH_*`.

> **Проверка создания:** ClientID Workspace и Telemost заданы в secrets; оба токена валидны (ping / telemost 201 / disk 200). UI oauth.yandex.ru агент не открывает — факт подтверждён ответами API.

---

## Шаг 2. Права доступа (scopes)

В карточке приложения → **Доступ к данным** включите минимум:

**MVP**

- Почта SMTP — `mail:smtp`
- Почта IMAP (read-only) — `mail:imap_ro` — **для чтения входящих агентом/CLI**
- Телемост — `telemost-api:conferences.create`, `telemost-api:conferences.read`
- Календарь — `calendar:events.write` или `calendar:all` (что есть в UI)
- Диск (ops) — `cloud_api:disk.read` / `cloud_api:disk.write` (или эквивалент в UI)

**Не включать:** `mail:imap_full` (запись/удаление), addressbook как CRM.

После добавления `mail:imap_ro` **перевыпустите** `YANDEX_OAUTH_ACCESS_TOKEN` (старый токен scope не подхватит).

**Не включать (устарело):** полный IMAP без правил ПДн — см. код `mail_imap.py` (read-only + redact).

Если scopes Телемоста требуют организацию 360 — оформите 360 или используйте ручные ссылки.  
На 2026-07-28 create conference через API **успешен** на токене Telemost-приложения.

Актуальный список прав смотрите в UI и в [доке Телемост access](https://yandex.ru/dev/telemost/doc/ru/access).

---

## Шаг 3. Получить OAuth-токен

### Вариант A — быстрый (для MVP / одного сервера)

Подставьте ClientID:

```text
https://oauth.yandex.ru/authorize?response_type=token&client_id=CLIENT_ID
```

1. Войдите как `proverkastaza@yandex.ru`.
2. Разрешите доступ.
3. Скопируйте `access_token` из redirect URL (фрагмент `#access_token=…`).

> Токен может иметь срок жизни. Запланируйте перевыпуск или перейдите на code + refresh (вариант B).

### Вариант B — authorization code (предпочтительно для production)

1. Authorize с `response_type=code&redirect_uri=…`.
2. Обмен code → `access_token` + `refresh_token` по доке OAuth.
3. Настроить автообновление в `integrations/yandex_workspace/oauth.py` (когда модуль появится).

---

## Шаг 4. Секреты

Локально (не коммитить):

`secrets/yandex-workspace.env`:

```text
YANDEX_OAUTH_CLIENT_ID=…
YANDEX_OAUTH_CLIENT_SECRET=
YANDEX_OAUTH_ACCESS_TOKEN=…
YANDEX_OAUTH_REFRESH_TOKEN=
YANDEX_WORKSPACE_EMAIL=proverkastaza@yandex.ru
YANDEX_TELEMOST_ENABLED=true
YANDEX_MAIL_ENABLED=true
YANDEX_MAIL_IMAP_ENABLED=true
YANDEX_CALENDAR_ENABLED=true
YANDEX_DISK_ENABLED=true
# + YANDEX_TELEMOST_OAUTH_* для SFRFR_telemost
```

На VPS: те же ключи в `/opt/sfrfr/.env` (или include файла), затем:

```bash
sudo systemctl restart sfrfr-api
```

**Не** класть токен в WordPress, фронт admin bundle, Notion, чаты.

---

## Шаг 5. Проверки после появления кода

| Проверка | Ожидание |
|----------|----------|
| `sfrfr yandex-workspace-ping` | `ok`, login `proverkastaza` |
| `sfrfr yandex-disk-status` | `ok`, папки `disk:/SFRFR-ops` и `disk:/SFRFR-cases` |
| `sfrfr yandex-telemost-create -c <uuid>` | `join_url` **или** `403 ApiRestrictedToOrganizations` → нужен Яндекс 360 |
| `sfrfr yandex-mail-send --to you@… -t request_docs` | `ok` при scope `mail:smtp` |
| `sfrfr yandex-mail-imap-ping` | `ok`, `messages_total` при `mail:imap_ro` + `YANDEX_MAIL_IMAP_ENABLED=true` |
| `sfrfr yandex-mail-list --limit 5` | список входящих (метаданные) |
| `sfrfr calendar-create …` | Google + Яндекс (dual-write) |
| Admin: кнопки «Создать Телемост» / «Письмо» | audit + `meeting_url` |

> **Почта SMTP/IMAP (проверено 2026-07-27):** после включения в настройках Почты IMAP + OAuth-токены — `smtp` и `imap` с XOAUTH2 работают на `proverkastaza@yandex.ru`.
>
> **Телемост API (проверено 2026-07-28):** create → **201** + `join_url` на токене `SFRFR_telemost`.
>
> **Календарь CalDAV** — PROPFIND 207, create 201. **Диск** — API 200; продукт: `YANDEX_DISK_ENABLED=true`, `SFRFR-ops` + зеркало `SFRFR-cases/{case_id}`.

Документация создания конференций: [Телемост API](https://yandex.ru/dev/telemost/doc/ru/).

---

## Шаг 6. Ротация и отзыв

1. [oauth.yandex.ru](https://oauth.yandex.ru/) → приложение → отозвать / сменить secret.
2. Пользователь: [https://passport.yandex.ru/profile](https://passport.yandex.ru/profile) → приложения с доступом.
3. Обновить token на VPS, restart API.
4. Запись в ops-журнале / `docs/history`.

---

## Частые ошибки

| Симптом | Что проверить |
|---------|----------------|
| `Invalid scope` | Scope не включён в приложении или нужен 360 |
| `Unauthorized` | Просроченный token / не тот аккаунт |
| Письма в спам | SPF/DKIM домена (если шлёте не с `@yandex.ru`, а с корпоративного домена) |
| Путаница с AI | Используете `YANDEX_API_KEY` вместо OAuth — это Cloud, не почта |

---

## Связь с AI Studio

| Переменная | Контур |
|------------|--------|
| `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_MODEL` | Cloud / GPT / Vision |
| `YANDEX_OAUTH_*`, `YANDEX_WORKSPACE_*` | ТЗ-14 Workspace |

Не переиспользовать один секрет на оба контура.
