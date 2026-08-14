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
| Быстрые ссылки (навигация в выдаче) | ⏳ формирует робот; UI: Представление в поиске → Быстрые ссылки (API не управляет) |
| FAQPage JSON-LD на главной | ✅ MU `sfrfr-seo-meta.php` |
| Навигационная цепочка (BreadcrumbList) | ✅ JSON-LD + видимые крошки на страницах/статьях |
| Главное зеркало HTTPS без www (301) | ✅ Apache |
| Recrawl после сида / вручную | ✅ `scripts/yandex_webmaster_recrawl.py` |
| Популярные запросы (H3/H5) | ✅ `scripts/yandex_webmaster_search_queries.py`; съём 2026-08-14: 1 запрос, 0 по калькулятору |
| Summary / host loaded | ✅ `data_status=OK`; **смотрите хост без www** |
| Страницы в поиске (apex) | ⏳ `searchable_pages_count=8` (04.08.2026); в sitemap **39** URL — лаг индексации |
| Обход по счётчикам Метрики | ⚠️ UI: ещё нужно включить (`NO_METRIKA_COUNTER_CRAWL_ENABLED=PRESENT`, 05.08.2026) |
| Страницы в поиске (www) | ⚠️ всегда **0** — ожидаемо: `www` → 301 на apex |
| Демо `sample-page` из индекса | ✅ draft (`wp_fix_sample_page.php`) |
| Clean-param в robots | ✅ MU `sfrfr-seo-robots.php`: ПДн и рекламные метки |
| Диагностика API | `python scripts/yandex_webmaster_host_diag.py` |
| Favicon `/favicon.ico` | ✅ + `/favicon.svg`, `/favicon-120.png` |
| Яндекс Бизнес (Sprav) | ✅ профиль `82469923047`, прайс: `docs/ops/yandex-business-profile.md` |
| Регион сайта | ⚠️ задать в UI Вебмастера (Ноябрьск / Россия) |
| SEO этап 4 (семантика / спринт) | [seo-semantics-map.md](seo-semantics-map.md), [seo-sprint.md](seo-sprint.md), [seo-hypothesis-log.md](seo-hypothesis-log.md) |
| Ручной UI-чеклист | [seo-webmaster-ui-checklist.md](seo-webmaster-ui-checklist.md) |

---

## Диагностика Вебмастера: что чинить, что нет

Смотрите рекомендации на хосте **`https://proverkastaza.ru`**, не на www.

| Рекомендация | Действие |
|---|---|
| Favicon / SVG / 120×120 | ✅ `/favicon.svg`, `/favicon-120.png` + link в `wp_head` |
| Укажите регион сайта | **Только UI:** Информация о сайте → Регион → **Ноябрьск** (юр. адрес) или **Россия** (онлайн по всей РФ) → [Задать регион](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/indexing/region/) |
| Добавьте в Яндекс Бизнес | Профиль уже есть (`82469923047`). В Sprav: сайт = `https://proverkastaza.ru`. Затем в Вебмастере подождать перепроверки или привязать организацию. |
| Счётчик Метрики не на всех страницах | ✅ код на всех страницах; для роботов Яндекса — без cookie-баннера |
| Sitemap | ✅ `https://proverkastaza.ru/wp-sitemap.xml` в robots + API (`yandex_webmaster_ensure_site.py`) |
| Счётчик Метрики не привязан | **В UI:** Настройки → Яндекс Метрика → привязать счётчик к хосту без www + включить обход. |
| NO_SITEMAPS (иногда) | Sitemap уже в API; при флаге — перепроверить раздел «Файлы Sitemap» на apex. |

«Самостоятельные проверки» (уведомления, целевые запросы) — чеклист UI, не ошибки сайта.

`Clean-param` исключает из уникальности страниц параметры с ПДн и рекламные метки:
`utm_*`, `yclid`, `ysclid`, `gclid`, `gad_*`, `gbraid`, `wbraid`, `fbclid`,
`vkclid`, `mt_click_id`, `_erid`, `erid`, `_openstat`, `referral_code`,
`campaign_code`. Канонический URL и сами переходы с метками остаются доступными.


Письмо/экран Вебмастера про **`https://www.proverkastaza.ru`** показывает **0** страниц — так и должно быть:

1. `www` и apex в Вебмастере — **разные хосты**.
2. Сервер отвечает **301** `https://www…` → `https://proverkastaza.ru/…`.
3. В поиске копятся URL **главного зеркала** (без www).

**Что открыть в UI:** сайт **`https://proverkastaza.ru`** (без www) → Индексирование → Страницы в поиске.

На 02.08.2026 там уже **8 SEARCHABLE**, в т.ч.:

- `/`
- `/blog/`
- `/blog/kak-proverit-stazh-v-vypiske-ils/`
- `/blog/severnyy-stazh-i-rayonnyy-koefficient/`
- `/blog/edv-i-pensiya-chto-proveryat-otdelno/`
- `/blog/lgotnyy-i-pedagogicheskiy-stazh/`
- `/blog/rashozhdeniya-fio-i-zapisi-trudovoy/`
- `/cookies/`

Фраза «на сайте изменений нет» в письме про www означает: **у зеркала www своего контента нет** (только редиректы), а не что сайт пустой.

### Диагностика хостов

| Host | searchable |
|------|------------|
| `https://proverkastaza.ru` | **8** (рабочий) |
| `http://proverkastaza.ru` | 0 (только 301 → https) |
| `https://www.proverkastaza.ru` | 0 (только 301 → apex) |
| `http://www.proverkastaza.ru` | 0 |

### Привязка Метрики и «Обход по счётчикам»

**Публичного API для этих двух шагов нет** (проверено: `POST/PUT …/metrika/*` → 404).  
Скрипт проверки: `python scripts/yandex_webmaster_link_metrika.py`.

| Шаг | Как |
|---|---|
| 1. Счётчик на сайте | ✅ уже: `111134477`, MU `sfrfr-yandex-metrika.php` |
| 2. Привязка к хосту | ✅ `NO_METRIKA_COUNTER_BINDING=ABSENT` (счётчик привязан) |
| 3. Включить обход | ⚠️ **сделать в UI** — диагностика `NO_METRIKA_COUNTER_CRAWL_ENABLED=PRESENT` (05.08.2026) |

Письмо Вебмастера «Обновление поисковой базы… изменений нет» — это **отчёт об индексе**, не о правках HTML. Sitemap уже в robots/API; ускорение = включить обход Метрики + переобход (скрипт `yandex_webmaster_recrawl.py`).

Кабинет: [список сайтов](https://webmaster.yandex.ru/sites/) → в шапке выбрать **`https://proverkastaza.ru`** (без www).

Прямые ссылки (после логина; host_id **обязательно** с `%3A`, иначе 404):

- [Сводка apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/dashboard/)
- [Настройки (привязка Метрики)](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/settings/)
- [Метрика счётчика](https://metrika.yandex.ru/settings?id=111134477)

Не открывайте `.../site/https:proverkastaza.ru:443/` без кодирования — браузер покажет 404.



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
