# Отслеживание статусов доработанных страниц — базовый снимок 2026-09-27

Страницы, доработанные в PR #100–#104, и посадочные из мониторинга Вебмастера.
Источник: API Вебмастера v4 (important-urls, in-search/indexing samples, recrawl queue) + живой ответ сайта.
Без ПДн и без поисковых запросов посетителей.

- Конфиг URL: `scripts/assets/seo/webmaster-tracked-urls.json`
- Базовый снимок (JSON): `docs/marketing-sales/reports/seo-page-status-baseline-2026-09-27.json`
- Повторный запуск (было → стало):

```powershell
.\.venv\Scripts\python.exe scripts/yandex_webmaster_url_status.py
```

- Ежедневно: workflow `webmaster-diagnostics-daily.yml` (09:15 МСК) — таблица и сравнение в job summary и артефакте.

## Критерии успеха (дедлайн 2026-10-11, промежуточно 2026-10-04)

1. Доработанные страницы (ожидаем «в поиске») — в поиске, без исключения LOW_QUALITY.
2. ЕДВ (`noindex`) — выпала из поиска, сайт отдаёт noindex.
3. Склеенные URL — 301 на целевые, сами не в поиске.

Если страница осталась LOW_QUALITY к 2026-10-11: сверить спрос (Wordstat) и каннибализацию с посадочной →
усилить уникальный блок или склеить 301 на посадочную / поставить noindex → переобход.

## Статусы страниц в Вебмастере — 2026-09-27T21:05+05:00

Цель достигнута: **23 из 29**. ✅ — статус совпал с ожидаемым, ⏳ — ещё нет. Поисковые запросы посетителей не выгружаются.

| URL | Группа | Ожидаем | Статус в поиске | Обход | Переобход | Ответ сайта | Цель |
|---|---|---|---|---|---|---|---|
| `/proverka-stazha-pered-pensiey/` | PR #100 | в поиске | исключена: LOW_QUALITY | 2026-09-26 | DONE | 200 | ⏳ |
| `/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/` | PR #100 | 301 → цель | нет в поиске | 2026-08-03 | DONE | 301 → /arhivnaya-spravka-stazh/ | ✅ |
| `/blog/otkaz-sfr-chto-proverit-v-dokumentah/` | PR #100 | в поиске | в поиске | 2026-09-08 | IN_PROGRESS | 200 | ✅ |
| `/blog/severnyy-stazh-i-rayonnyy-koefficient/` | PR #100 | в поиске | в поиске | 2026-09-18 | DONE | 200 | ✅ |
| `/blog/chto-delat-esli-period-raboty-ne-uchten/` | склейка | 301 → цель | нет в поиске | 2026-09-13 | DONE | 301 → /ne-uchli-stazh/ | ✅ |
| `/blog/kak-pomoch-rodstvenniku-proverit-stazh/` | склейка | 301 → цель | нет в поиске | — | DONE | 301 → /pomoch-rodstvenniku-proverit-stazh/ | ✅ |
| `/pomoch-rodstvenniku-proverit-stazh/` | PR #101 | в поиске | исключена: LOW_QUALITY | 2026-08-30 | IN_PROGRESS | 200 | ⏳ |
| `/blog/kak-zakazat-vypisku-ils/` | PR #101 | в поиске | исключена: LOW_QUALITY | 2026-09-04 | IN_PROGRESS | 200 | ⏳ |
| `/blog/lgotnyy-i-pedagogicheskiy-stazh/` | PR #101 | в поиске | исключена: LOW_QUALITY | 2026-08-23 | DONE | 200 | ⏳ |
| `/blog/rashozhdeniya-fio-i-zapisi-trudovoy/` | PR #102 | в поиске | исключена: LOW_QUALITY | 2026-09-26 | DONE | 200 | ⏳ |
| `/blog/edv-i-pensiya-chto-proveryat-otdelno/` | PR #102 | noindex, выпасть | нет в поиске | 2026-08-26 | DONE | 200, noindex | ✅ |
| `/expert/lopakova-nataliya/` | PR #103/#104 | в поиске | исключена: LOW_QUALITY | 2026-09-03 | DONE | 200 | ⏳ |
| `/expert/bogdanovskiy-sergey/` | PR #103/#104 | в поиске | в поиске | 2026-09-18 | IN_PROGRESS | 200 | ✅ |
| `/` | посадочная | в поиске | в поиске | 2026-09-26 | DONE | 200 | ✅ |
| `/ne-uchli-stazh/` | посадочная | в поиске | в поиске | 2026-09-08 | DONE | 200 | ✅ |
| `/arhivnaya-spravka-stazh/` | посадочная | в поиске | в поиске | 2026-09-27 | IN_PROGRESS | 200 | ✅ |
| `/stazh-do-2002/` | посадочная | в поиске | в поиске | 2026-09-09 | DONE | 200 | ✅ |
| `/otkaz-sfr/` | посадочная | в поиске | в поиске | 2026-09-08 | DONE | 200 | ✅ |
| `/chek-list-dokumentov/` | посадочная | в поиске | в поиске | 2026-09-18 | DONE | 200 | ✅ |
| `/proverka-stazha/` | посадочная | в поиске | в поиске | 2026-09-16 | DONE | 200 | ✅ |
| `/proverka-severnogo-stazha/` | посадочная | в поиске | в поиске | 2026-09-18 | DONE | 200 | ✅ |
| `/tarify/` | посадочная | в поиске | в поиске | 2026-09-26 | DONE | 200 | ✅ |
| `/blog/kak-sverit-trudovuyu-knizhku-i-ils/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-13 | DONE | 200 | ✅ |
| `/kak-rabotaem/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-18 | DONE | 200 | ✅ |
| `/blog/kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-08 | DONE | 200 | ✅ |
| `/oferta/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-04 | DONE | 200 | ✅ |
| `/kontakty/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-03 | IN_PROGRESS | 200 | ✅ |
| `/blog/kak-proverit-stazh-v-vypiske-ils/` | мониторинг Вебмастера | в поиске | в поиске | 2026-09-16 | DONE | 200 | ✅ |
| `/blog/` | мониторинг Вебмастера | в поиске | в поиске | 2026-08-22 | DONE | 200 | ✅ |
