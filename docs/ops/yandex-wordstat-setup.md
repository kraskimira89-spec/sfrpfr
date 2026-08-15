# Яндекс Wordstat API (Search API v2)

**Сайт / задача:** частоты для [research 7 кластеров](../marketing-sales/research-seo-problem-clusters-wordstat-2026-08.md)  
**Скрипт:** `scripts/wordstat_fetch_7_clusters.py`  
**Секрет:** `secrets/yandex-wordstat.env` (gitignore) — `YANDEX_WORDSTAT_API_KEY`, `YANDEX_WORDSTAT_FOLDER_ID`

Официально: [API Вордстата → Search API](https://yandex.ru/support2/wordstat/ru/content/api-wordstat).

## Доступ

1. Каталог Yandex Cloud + **активный биллинг**.
2. Сервисный аккаунт с ролью на каталоге:
   - `search-api.webSearch.user` и/или `search-api.executor`
3. API-ключ SA со scope **`yc.search-api.execute`** (не путать с ключом только для LLM).
4. Ключ LLM из `secrets/yandexAI_studio.env` **без** Search-роли даёт `403 Permission denied`.

## Запуск

```powershell
.\.venv\Scripts\Activate.ps1
# smoke
python scripts/wordstat_fetch_7_clusters.py --phrase "не учли стаж в ИЛС" --no-geo
# дозаполнить TBD (РФ + гео)
python scripts/wordstat_fetch_7_clusters.py
# только РФ (экономит квоту)
python scripts/wordstat_fetch_7_clusters.py --no-geo
# перезаписать всё
python scripts/wordstat_fetch_7_clusters.py --all --no-geo
```

Квота (на 2026-08): **~100 запросов Wordstat / час**. С гео (РФ + 4 региона) ≈ 5 запросов на фразу. При `429` скрипт ждёт и ретраит; прогресс пишется в CSV после каждой фразы.

Регионы в скрипте 7 кластеров: РФ `225`, Москва `213`, СПб `2`, **ЯНАО `11232`**, ХМАО `11193`, плюс Мурманск/Архангельск/Коми/Карелия/Красноярск/Якутия.

**Север / АЗРФ / КС / приравненные:** справочник [wordstat-north-regions.json](../marketing-sales/reports/wordstat-north-regions.json), отчёт [wordstat-north-pensioners-2026-08-14.md](../marketing-sales/reports/wordstat-north-pensioners-2026-08-14.md), обход:

```powershell
python scripts/wordstat_fetch_north_regions.py --list
# до полного заполнения матрицы, не больше 80 req/час (запас до квоты 100)
python scripts/wordstat_fetch_north_regions.py --until-done --rph 80
# один проход без ожидания
python scripts/wordstat_fetch_north_regions.py --once
```

Файл прогресса: `docs/marketing-sales/reports/wordstat-north-geo-matrix.csv` (+ дневная копия). При 429 скрипт **не останавливается** — ждёт окно и продолжает.

Внимание: раньше ЯНАО ошибочно указывали как `10842` (это Архангельская область).

## Выход

- Обновляет `docs/marketing-sales/reports/wordstat-7-clusters-template.csv`
- Копия `wordstat-7-clusters-filled-YYYY-MM-DD.csv`
- Колонка `similar_top` — похожие + associations
