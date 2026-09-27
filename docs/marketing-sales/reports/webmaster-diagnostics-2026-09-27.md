# Диагностика Яндекс Вебмастера (2026-09-27)

Снято: `2026-09-27T12:07:59+03:00` (повторный прогон, первый — 07:16) · скрипт `scripts/yandex_webmaster_diagnostics.py`

**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).
Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.

UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)

## Apex (действия)

- searchable_pages: **24**
- excluded_pages: 1
- site_problems: `{}`

✅ Активных проблем на apex **нет**.

## Что нового в прогоне 12:07

- `admin.proverkastaza.ru` и `cabinet.proverkastaza.ru` появились в списке хостов Вебмастера (владелец добавил) — диагностика OK.
- Автоисправления: `ensure_site` OK, `after_probe` (robots, favicon, sitemap на живом сайте) OK. Шаг `vps_ssh` не выполнен: `ssh: connect to host … port 22: Connection timed out` (с этого ПК SSH нестабилен из-за VPN). Живые проверки чинить не пришлось — ошибок нет.
- **Напоминание владельцу (UI, кодом не чинится):** `NOT_IN_SPRAV` и `NO_REGIONS` сейчас видны только на зеркале `http://www` — на apex их нет. `NO_METRIKA_COUNTER_CRAWL_ENABLED` в этом прогоне не выдаётся. Если появятся на apex — Вебмастер → «Региональность» и привязка карточки Яндекс Бизнеса; Метрика → «Обход по счётчику».

## Мониторинг важных страниц (API `important-urls`, 12:08)

В списке 31 URL (владелец обновил сегодня).

| Статус | URL |
|---|---|
| В поиске (200) | `/`, `/blog/`, `/tarify/`, `/proverka-stazha/`, `/kak-rabotaem/`, `/proverka-severnogo-stazha/`, `/oferta/`, `/kontakty/`, `/blog/kak-sverit-trudovuyu-knizhku-i-ils/`, `/blog/otkaz-sfr-chto-proverit-v-dokumentah/`, `/blog/kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc/`, `/blog/kak-proverit-stazh-v-vypiske-ils/` |
| `LOW_QUALITY` (200) | `/expert/lopakova-nataliya/`, `/pomoch-rodstvenniku-proverit-stazh/`, `/proverka-stazha-pered-pensiey/`, `/blog/lgotnyy-i-pedagogicheskiy-stazh/`, `/blog/kak-zakazat-vypisku-ils/`, `/blog/chto-delat-esli-period-raboty-ne-uchten/` (уже 301, данные робота старые), `/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/`, `/blog/rashozhdeniya-fio-i-zapisi-trudovoy/`, `/blog/edv-i-pensiya-chto-proveryat-otdelno/` |
| Новые, данных ещё нет | `/o-servise/`, `/blog/kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr/`, `/stazh-do-2002/`, `/otkaz-sfr/`, `/ne-uchli-stazh/`, `/chek-list-dokumentov/`, `/arhivnaya-spravka-stazh/` |
| 301 | `/blog/primer-rabotodatel-v-trudovoy-net-v-ils/` → `/ne-uchli-stazh/` (ожидаемо) |
| 404 | `/blog/kak-sverit-trudovuyu-s-vypiskoy-ils/`, `/blog/chto-delat-esli-period-ne-voshel-v-stazh/` |

**Владельцу (UI):** удалить из мониторинга два URL с 404 и `/blog/primer-rabotodatel-v-trudovoy-net-v-ils/` (301). После деплоя раунда 3 статьи `/blog/chto-delat-esli-period-raboty-ne-uchten/` и `/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/` отдают 301 на посадочные (они уже в мониторинге) — статьи из мониторинга можно убрать. `/o-servise/` — в аудите отдавала 404, проверить, нужна ли она в списке.

По событиям выдачи (`search-urls/events`): 27.09 в поиск попали `/chek-list-dokumentov/pechat/` и `/chek-list-dokumentov/a4/` (у `a4` с #96 стоит `noindex` — выпадет после переобхода). 23.09 появились `/tarify/`, `/otzyvy/`, `/expert/`, `/cookies/`, `/blog/kak-sverit-trudovuyu-knizhku-i-ils/`, `/chek-list-dokumentov/`.

Рекомендации по страницам `LOW_QUALITY`: [seo-low-quality-recommendations-2026-09-27.md](seo-low-quality-recommendations-2026-09-27.md).

## Все хосты (справка)

### https://admin.proverkastaza.ru
- diagnostics: OK

### https://cabinet.proverkastaza.ru
- diagnostics: OK

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

## Автоисправления (прогон 12:07)

- OK `ensure_site`
- FAIL `vps_ssh` — таймаут SSH с локального ПК; на VPS ремедиацию выполняет workflow `webmaster-diagnostics-daily.yml`
- OK `after_probe`

## Как обновить

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/yandex_webmaster_diagnostics.py --report --fix --ssh
```
