# Яндекс Вебмастер для SFRFR

**Сайт:** `https://proverkastaza.ru`  
Отдельно от Метрики (`secrets/yandex-metrika.env`) и Cloud AI.

---

## OAuth (только в браузере)

1. [oauth.yandex.ru](https://oauth.yandex.ru/) → приложение **SFRFR Webmaster** (тип «Для доступа к API»).
2. Redirect URI: `https://oauth.yandex.ru/verification_code`.
3. Права: **`webmaster:hostinfo`**, **`webmaster:verify`** (без turbopages / suggest).
4. Токен:

```text
https://oauth.yandex.ru/authorize?response_type=token&client_id=CLIENT_ID
```

В `access_token` должен быть **`y0_…`**, не ClientID.

Секреты: `secrets/yandex-webmaster.env` (gitignore).

---

## API ensure

```powershell
python scripts/yandex_webmaster_ensure_site.py
```

Скрипт: хост → META_TAG verification → sitemap (`wp-sitemap.xml`).

### Текущее состояние (2026-07-29)

| Host ID | Статус |
|---------|--------|
| `http:proverkastaza.ru:80` | VERIFIED |
| `https:proverkastaza.ru:443` | VERIFIED (основной) |
| `http:www.proverkastaza.ru:80` | VERIFIED |
| `https:www.proverkastaza.ru:443` | VERIFIED |

**UIN meta:** `24f89ecf6ff4297b`  
**Sitemap в API:** `https://proverkastaza.ru/wp-sitemap.xml`  
(тот же URL в `robots.txt` WordPress.)

User ID Webmaster API: `2412411947`.

---

## Главное зеркало (HTTPS без www)

API Вебмастера **не умеет** задать главное зеркало — только читает `main_mirror` после обхода роботом.

Сделано на сервере (Apache):

- `http://` и `http://www.` → `https://proverkastaza.ru/…` (один 301)
- `https://www.` → `https://proverkastaza.ru/…` (301)

Конфиги: `docs/apache-vhost-proverkastaza.ru.conf`, `docs/apache-vhost-proverkastaza.ru-le-ssl.conf`.

Пока `host_data_status=NOT_LOADED` / `main_mirror=null` — нормально; после индексации Яндекс подхватит apex.

В UI: [Webmaster](https://webmaster.yandex.ru/) → сайт → «Главное зеркало» (контроль).

---

## Не коммитить

- `secrets/yandex-webmaster.env`
- OAuth `access_token` / Client Secret
