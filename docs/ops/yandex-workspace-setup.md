# Настройка Яндекс Workspace (OAuth) для SFRFR

**ТЗ:** [../specs/14-yandex-workspace.md](../specs/14-yandex-workspace.md)  
**Аккаунт:** `proverkastaza@yandex.ru`  
**Версия гайда:** 1.0 (2026-07-27)

Отдельно от **Yandex Cloud AI Studio** (`YANDEX_API_KEY` / `folder_id`) — здесь только доступ к почте / Телемосту / календарю / (опц.) Диску.

---

## Что понадобится

- Браузер, вход в `proverkastaza@yandex.ru`
- Права менять VPS `.env` / `secrets/`
- Callback URL API (или ручной выпуск токена на первом этапе)

---

## Шаг 0. Решить контур

| Вопрос | MVP |
|--------|-----|
| Личный ящик `@yandex.ru` или Яндекс 360? | Начать с личного; 360 — если Телемост API/scopes недоступны |
| Нужен ли Диск? | **Нет** по умолчанию (`YANDEX_DISK_ENABLED=false`) |
| Дублировать Google Calendar? | Либо Яндекс, либо Google — не оба как source of truth |

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

---

## Шаг 2. Права доступа (scopes)

В карточке приложения → **Доступ к данным** включите минимум:

**MVP**

- Почта SMTP — `mail:smtp`
- Телемост — `telemost-api:conferences.create`, `telemost-api:conferences.read`
- Календарь — `calendar:events.write` или `calendar:all` (что есть в UI)

**Не включать сразу:** полный Диск write, IMAP full, addressbook — пока нет реализации и политики ПДн.

Если scopes Телемоста требуют организацию 360 — оформите 360 или отложите этап A до ручных ссылок.

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
YANDEX_CALENDAR_ENABLED=true
YANDEX_DISK_ENABLED=false
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
| `sfrfr yandex-workspace-ping` | `ok` / scopes видны |
| Создать Телемост на тестовом `case_id` | URL `https://telemost.yandex.ru/…` |
| Тестовое письмо на свой ящик | From = `proverkastaza@yandex.ru` |
| Disk API | не вызывается при `YANDEX_DISK_ENABLED=false` |

Пока модуля нет — проверки вручную:

```bash
curl -s -H "Authorization: OAuth $YANDEX_OAUTH_ACCESS_TOKEN" \
  https://cloud-api.yandex.net/v1/disk/
```

(Диск — только smoke OAuth; для MVP Диск выключен.)

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
