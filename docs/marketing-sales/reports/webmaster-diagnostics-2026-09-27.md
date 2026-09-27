# Диагностика Яндекс Вебмастера (2026-09-27)

Снято: `2026-09-27T07:16:00+03:00` · скрипт `scripts/yandex_webmaster_diagnostics.py`

**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).
Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.

UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)

## Apex (действия)

- searchable_pages: **24**
- excluded_pages: 1
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

## Поддомены в поиске (письмо Вебмастера, пример admin.proverkastaza.ru)

Справка: [Как скрыть страницы от робота](https://yandex.ru/support/webmaster/ru/robot-workings/unhelpful)
(старый адрес `robot-workings/subdomains` отдаёт 404). Канон: у каждого поддомена свой
`robots.txt` с `User-agent: *` / `Disallow: /` + `noindex`.

| Поддомен | Было (live, до PR) | Стало (после деплоя) |
|----------|--------------------|----------------------|
| `admin` (Next.js :3002) | `/robots.txt` → 404 HTML, `X-Robots-Tag` нет | `app/robots.ts` → `Disallow: /`, заголовок `noindex, nofollow`, meta robots в layout |
| `cabinet` (Next.js :3001) | то же | то же |
| `api` (FastAPI :8011) | `/robots.txt` → 404 JSON, `X-Robots-Tag` нет | маршрут `/robots.txt` → `Disallow: /`, middleware `X-Robots-Tag` на всех ответах |
| `supabase` (Caddy, ВМ Yandex Cloud) | 401 на всё (basic auth) | без изменений: 401 не индексируется; деплоится не через `deploy-vps` |
| wildcard `*.proverkastaza.ru` | NXDOMAIN | закрывать нечего |

Основной сайт и зеркала `www`/`http` не менялись: robots apex — WordPress, `Disallow: /wp-admin/` + sitemap.

Закрытие сделано на уровне приложений, потому что Apache-vhost'ы (`docs/apache-vhost-*.conf`)
ставятся только вручную `scripts/vps_cutover_proverkastaza.sh`, а не `deploy-vps`.
Резервный вариант на VPS (вручную, в `<VirtualHost>` admin/cabinet/api):

```apache
Header always set X-Robots-Tag "noindex, nofollow"
```

(нужен `a2enmod headers`, затем `apachectl configtest && systemctl reload apache2`).

**Владельцу в Вебмастере (UI):**

1. Добавить `https://admin.proverkastaza.ru` (и при появлении в поиске — `cabinet`, `api`) как отдельные сайты, подтвердить права.
2. Инструменты → «Анализ robots.txt»: убедиться, что `/` запрещён.
3. Инструменты → «Удаление страниц из поиска» → «По префиксу» `https://admin.proverkastaza.ru/`.

## Как обновить

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/yandex_webmaster_diagnostics.py --report --fix --ssh
```
