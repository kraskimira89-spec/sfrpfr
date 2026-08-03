# Яндекс Вебмастер для SFRFR

**Сайт:** `https://proverkastaza.ru`  
Отдельно от Метрики (`secrets/yandex-metrika.env`) и Cloud AI.

---

## Статус внедрения (чеклист)

| Раздел | Статус |
|--------|--------|
| OAuth `webmaster:hostinfo` + `verify` | ✅ |
| Хосты http/https ± www VERIFIED | ✅ |
| META UIN на WP | ✅ `24f89ecf6ff4297b` |
| Sitemap `wp-sitemap.xml` в API + robots | ✅ |
| Главное зеркало HTTPS без www (301) | ✅ Apache |
| Recrawl после сида / вручную | ✅ `scripts/yandex_webmaster_recrawl.py` |
| Summary / host loaded | ✅ `data_status=OK` (ранее NOT_LOADED); searchable≈8, смотреть диагностику |
| Демо `sample-page` из индекса | ✅ draft (`wp_fix_sample_page.php`) |
| Clean-param в robots | ✅ MU `sfrfr-seo-robots.php` |

---

## OAuth (только в браузере)

1. [oauth.yandex.ru](https://oauth.yandex.ru/) → **SFRFR Webmaster**.
2. Redirect URI: `https://oauth.yandex.ru/verification_code`.
3. Права: **`webmaster:hostinfo`**, **`webmaster:verify`**.
4. Токен `y0_…` → `secrets/yandex-webmaster.env`.

---

## API ensure + recrawl

```powershell
python scripts/yandex_webmaster_ensure_site.py
python scripts/yandex_webmaster_recrawl.py
# или точечно:
python scripts/yandex_webmaster_recrawl.py https://proverkastaza.ru/blog/...
```

Ensure: хост → META_TAG → sitemap → статус host/summary.  
Recrawl: очередь переобхода (суточная квота Яндекса).

После `wp_seed_site_tz02.sh` recrawl вызывается сам, если есть `secrets/yandex-webmaster.env`.

### Хосты

| Host ID | Статус |
|---------|--------|
| `https:proverkastaza.ru:443` | VERIFIED (основной) |
| `http:proverkastaza.ru:80` | VERIFIED |
| `https:www…` / `http:www…` | VERIFIED |

User ID: `2412411947`.

---

## Главное зеркало (HTTPS без www)

API только **читает** `main_mirror`. На сервере:

- `http://` и `http://www.` → `https://proverkastaza.ru/…`
- `https://www.` → `https://proverkastaza.ru/…`

Конфиги: `docs/apache-vhost-proverkastaza.ru.conf`, `*-le-ssl.conf`.

---

## Не коммитить

- `secrets/yandex-webmaster.env`
- OAuth token / Client Secret
