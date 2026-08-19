# Чеклист UI Яндекс Вебмастера (ручные пункты)

**Хост:** только `https://proverkastaza.ru` (без www).  
**Ops API:** [yandex-webmaster-setup.md](yandex-webmaster-setup.md).

| # | Действие | Где в UI | Статус владельца | Зачем |
|---|---|---|---|---|
| 1 | Задать **регион сайта: Россия** | Кабинет: [список сайтов](https://webmaster.yandex.ru/sites/) → хост **без www** → **Представление в поиске → Региональность**. [Как выбрать регион](https://yandex.ru/support/webmaster/ru/site-geography/site-region#choose): юр. адрес Ноябрьск, услуга по РФ — на `/kontakty/` и в футере это написано. Ссылка для модератора: [контакты](https://proverkastaza.ru/kontakty/). Прямой `/indexing/region/` — 404. | ☐ владелец | Релевантность по геозависимым запросам по РФ. API нет. |
| 2 | Привязать счётчик **Метрики** к apex | Настройки → Яндекс Метрика | ☐ | Связка аналитики и Вебмастера |
| 3 | Включить **обход по счётчикам Метрики** | Настройки / рекомендации диагностики | ☐ | Ускорение обхода новых URL |
| 4 | Проверить раздел **Sitemap** на apex | Индексирование → Файлы Sitemap | ☐ | `wp-sitemap.xml` уже в API/robots |
| 5 | Мониторить **быстрые ссылки** | Представление в поиске | ☐ | Робот формирует сам; sitelink titles на сайте уже готовят |
| 6 | После правок title — **переобход** | Переобход страниц или `scripts/yandex_webmaster_recrawl.py` | ☐ | Этап 4 / гипотезы H3–H4 |
| 7 | Прогнать **диагностику API** | `python scripts/yandex_webmaster_diagnostics.py --report` | ☐ | Без почты; apex без PRESENT = OK |

Секреты (`y0_…`) только в `secrets/yandex-webmaster.env`, не в git.

После выполнения пункта — отметить здесь и одной строкой в [seo-hypothesis-log.md](seo-hypothesis-log.md).
