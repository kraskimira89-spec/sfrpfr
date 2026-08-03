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
| Summary / host loaded | ✅ `data_status=OK`; **смотрите хост без www** |
| Страницы в поиске (apex) | ✅ `searchable_pages_count=8` на `https://proverkastaza.ru` (02.08.2026) |
| Страницы в поиске (www) | ⚠️ всегда **0** — ожидаемо: `www` → 301 на apex |
| Демо `sample-page` из индекса | ✅ draft (`wp_fix_sample_page.php`) |
| Clean-param в robots | ✅ MU `sfrfr-seo-robots.php` |
| Диагностика API | `python scripts/yandex_webmaster_host_diag.py` |
| Favicon `/favicon.ico` | ✅ файл в корне WP (`scripts/assets/favicon.ico`) |

---

## Диагностика Вебмастера: что чинить, что нет

Смотрите рекомендации на хосте **`https://proverkastaza.ru`**, не на www.

| Рекомендация | Действие |
|---|---|
| Favicon не найден | Было: `/favicon.ico` отдавал HTML. Сейчас — реальный ICO. Переобход главной. |
| Счётчик Метрики не привязан | **В UI:** Настройки → Яндекс Метрика → привязать счётчик к хосту без www + включить обход. |
| Добавить в Яндекс Бизнес | Опционально (карты/сниппеты). Не блокирует индекс. |
| NO_SITEMAPS (иногда) | Sitemap уже в API; при флаге — перепроверить раздел «Файлы Sitemap» на apex. |

«Самостоятельные проверки» (уведомления, целевые запросы) — чеклист UI, не ошибки сайта.


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
| 2. Привязка к хосту | **UI** на `https://proverkastaza.ru` (не www): Настройки → Привязка к Яндекс Метрике → добавить `111134477` |
| 3. Включить обход | **UI**: Индексирование → Обход по счётчикам → вкл. |

Кабинет apex: https://webmaster.yandex.ru/site/https:proverkastaza.ru:443/



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
