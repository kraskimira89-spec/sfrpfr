# Яндекс Метрика для SFRFR (вариант B: API + код на WP)

**Сайт:** `https://proverkastaza.ru`  
**Правило ПДн:** в цели/URL/params — только коды (`lead_ok`, `max_click`), без телефонов/ФИО/email.

Отдельно от Workspace OAuth (`secrets/yandex-workspace.env`) и Cloud AI (`YANDEX_API_KEY`).

---

## Шаг 1 — OAuth-приложение (только вы в браузере)

1. Войти на [oauth.yandex.ru](https://oauth.yandex.ru/) под аккаунтом, который будет владельцем счётчика (удобно `proverkastaza@yandex.ru`).
2. **Создать новое приложение** → тип **«Для доступа к API или отладки»**.
3. Название: `SFRFR Metrika`.
4. Платформы: **Веб-сервисы**.
5. Redirect URI: `https://oauth.yandex.ru/verification_code` (для ручного токена).
6. **Доступы к данным** (отметить):
   - `metrika:read`
   - `metrika:write`
7. Сохранить → скопировать **ClientID**.

### Выпустить токен

Открыть в браузере (подставьте ClientID):

```text
https://oauth.yandex.ru/authorize?response_type=token&client_id=CLIENT_ID
```

После «Разрешить» скопировать `access_token` из адресной строки.

### Записать секреты

Локально: `secrets/yandex-metrika.env` (gitignore):

```env
YANDEX_METRIKA_OAUTH_CLIENT_ID=
YANDEX_METRIKA_OAUTH_ACCESS_TOKEN=
YANDEX_METRIKA_SITE_URL=https://proverkastaza.ru
YANDEX_METRIKA_COUNTER_NAME=Проверка стажа
# После ensure-скрипта:
# YANDEX_METRIKA_COUNTER_ID=
```

На VPS в `/opt/sfrfr/.env` (или тот же secrets-файл + source):

```env
YANDEX_METRIKA_COUNTER_ID=
YANDEX_METRIKA_WEBVISOR=0
```

`WEBVISOR=0` по умолчанию — включать только после маскирования полей ПДн.

---

## Шаг 2 — создать счётчик и цели (API)

```bash
# локально или на VPS
set -a && source secrets/yandex-metrika.env && set +a
python scripts/yandex_metrika_ensure_counter.py
```

Скрипт:

1. Ищет счётчик с site `proverkastaza.ru` или создаёт новый.
2. Создаёт JS-цели: `lead_ok`, `max_click` (если нет).
3. Печатает `YANDEX_METRIKA_COUNTER_ID=…` — дописать в `.env` / secrets.

---

## Шаг 3 — код на WordPress

```bash
# на VPS (после git pull + COUNTER_ID в /opt/sfrfr/.env)
sudo bash /opt/sfrfr/scripts/wp_deploy_metrika.sh
```

MU-plugin: `scripts/wp-mu-plugins/sfrfr-yandex-metrika.php`  
Читает `YANDEX_METRIKA_COUNTER_ID` из `/opt/sfrfr/.env`, вставляет счётчик в `wp_head`, вешает безопасные `reachGoal` на CTA MAX и success формы.

---

## Проверка

1. Открыть `https://proverkastaza.ru/` → DevTools → Network: запросы к `mc.yandex.ru`.
2. Метрика → счётчик → «Проверка счётчика» / онлайн-посетители.
3. Клик «Открыть в MAX» → цель `max_click`.
4. Тестовая заявка (без реальных ПДн в URL) → `lead_ok`.

---

## Когда готовы ClientID + token

Пришлите в чат **только ClientID** (не secret) и подтвердите, что токен лежит в `secrets/yandex-metrika.env` — агент прогонит ensure + деплой на VPS.
