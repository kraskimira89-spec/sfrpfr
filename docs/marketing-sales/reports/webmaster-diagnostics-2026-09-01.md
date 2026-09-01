# Диагностика Яндекс Вебмастера (2026-09-01)

Снято: `2026-09-01T12:16:22+03:00` · скрипт `scripts/yandex_webmaster_diagnostics.py`

**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).
Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.

UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)

## Apex (действия)

- searchable_pages: **7**
- excluded_pages: 0
- site_problems: `{}`

✅ Активных проблем на apex **нет**.

## Все хосты (справка)

### http://proverkastaza.ru
- diagnostics: OK

### https://proverkastaza.ru
- diagnostics: OK

### https://www.proverkastaza.ru
- diagnostics: OK

### http://www.proverkastaza.ru
- `MAIN_MIRROR_IS_NOT_HTTPS` (POSSIBLE_PROBLEM) _(зеркало, можно игнорировать)_
- `NOT_IN_SPRAV` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_REGIONS` (RECOMMENDATION) _(зеркало, можно игнорировать)_

## Автоисправления

- OK ensure_site
- OK vps_ssh remediate
ga-dobra/wp-content/mu-plugins/sfrfr-hide-astra-copyright.php
OK: /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-site-footer.php
OK: /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-blog-ui-assets/
OK: /var/www/taxi-doroga-dobra/favicon.ico
==> favicons in site root
OK: /var/www/taxi-doroga-dobra/favicon.ico
OK: /var/www/taxi-doroga-dobra/favicon.svg
OK: /var/www/taxi-doroga-dobra/favicon-120.png
==> webmaster ensure (sitemap API)
SKIP: no secrets/yandex-webmaster.env on VPS
==> cache flush
Success: The cache was flushed.
==> live probes
robots.txt 200
sitemap 200
home 200
HTTP/1.1 200 OK
Date: Tue, 01 Sep 2026 09:16:33 GMT
Server: Apache/2.4.52 (Ubuntu)
OK: vps_webmaster_remediate
From https://github.com/kraskimira89-spec/sfrpfr
 * branch            main       -> FETCH_HEAD

- after_probe: OK

## Как обновить

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/yandex_webmaster_diagnostics.py --report --fix --ssh
```
