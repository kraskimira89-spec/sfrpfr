# Диагностика Яндекс Вебмастера (2026-10-27)

Снято: `2026-10-27T08:00:09+03:00` · скрипт `scripts/yandex_webmaster_diagnostics.py`

**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).
Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.

UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)

## Apex (действия)

- searchable_pages: **35**
- excluded_pages: 4
- site_problems: `{}`

✅ Активных проблем на apex **нет**.

## Все хосты (справка)

### https://admin.proverkastaza.ru
- `DISALLOWED_IN_ROBOTS` (FATAL)
- `FAVICON_PROBLEM` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `MAIN_PAGE_ERROR` (FATAL)
- `NOT_IN_SPRAV` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_REGIONS` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_SITEMAPS` (POSSIBLE_PROBLEM)

### https://cabinet.proverkastaza.ru
- `DISALLOWED_IN_ROBOTS` (FATAL)
- `MAIN_PAGE_ERROR` (FATAL)
- `NOT_IN_SPRAV` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_REGIONS` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_SITEMAPS` (POSSIBLE_PROBLEM)

### http://proverkastaza.ru
- diagnostics: OK

### https://proverkastaza.ru
- diagnostics: OK

### https://www.proverkastaza.ru
- diagnostics: OK

### http://www.proverkastaza.ru
- diagnostics: OK

## Автоисправления

- OK ensure_site
- OK vps_ssh remediate
ins/sfrfr-seo-redirects.php
OK: /var/www/proverkastaza/wp-content/mu-plugins/sfrfr-hide-astra-copyright.php
OK: /var/www/proverkastaza/wp-content/mu-plugins/sfrfr-site-footer.php
OK: /var/www/proverkastaza/wp-content/mu-plugins/sfrfr-blog-ui-assets/
OK: /var/www/proverkastaza/favicon.ico
==> favicons in site root
OK: /var/www/proverkastaza/favicon.ico
OK: /var/www/proverkastaza/favicon.svg
OK: /var/www/proverkastaza/favicon-120.png
==> webmaster ensure (sitemap API)
SKIP: no secrets/yandex-webmaster.env on VPS
==> cache flush
Success: The cache was flushed.
==> live probes
robots.txt 200
sitemap 200
home 200
HTTP/1.1 200 OK
Date: Tue, 27 Oct 2026 05:00:25 GMT
Server: Apache
OK: vps_webmaster_remediate
From github.com:kraskimira89-spec/sfrpfr
 * branch              main       -> FETCH_HEAD

- after_probe: OK

## Как обновить

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/yandex_webmaster_diagnostics.py --report --fix --ssh
```
