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

Скрипт: `GET /v4/user` → список/добавление хоста → META_TAG verification.

### Текущее состояние (2026-07-29)

| Host ID | Статус |
|---------|--------|
| `http:proverkastaza.ru:80` | VERIFIED |
| `https:proverkastaza.ru:443` | VERIFIED (основной) |
| `http:www.proverkastaza.ru:80` | VERIFIED |
| `https:www.proverkastaza.ru:443` | VERIFIED |

**UIN meta:** `24f89ecf6ff4297b`  
На WP: MU-plugin `sfrfr-yandex-verification.php` (уже совпадает).

User ID Webmaster API: `2412411947`.

---

## Что дальше вручную в UI

1. В [Webmaster](https://webmaster.yandex.ru/) выбрать **https://proverkastaza.ru**.
2. Главное зеркало: без `www`, схема HTTPS.
3. Sitemap: `https://proverkastaza.ru/sitemap_index.xml` (или актуальный URL из Yoast/Rank Math).
4. Алиасы `prostaz.ru` / `proverka-staza.ru` — только если нужны как отдельные хосты; сейчас они 301 на основной.

---

## Не коммитить

- `secrets/yandex-webmaster.env`
- OAuth `access_token` / Client Secret
