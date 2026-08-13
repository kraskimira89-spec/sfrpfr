# 2026-08-13 — Wordstat API + частичная выгрузка 7 кластеров

## Сделано

1. `scripts/wordstat_fetch_7_clusters.py` — Search API v2 `topRequests`, инкрементальный CSV, retry 429.
2. `secrets/yandex-wordstat.env` (gitignore): ключ SA с `yc.search-api.execute` + роли `search-api.*` на folder.
3. Ops: `docs/ops/yandex-wordstat-setup.md`.
4. Выгрузка: **19/47** фраз с `freq_rf` + гео; дальше упёрлись в квоту **100 req/час**.
5. Снимок: `docs/marketing-sales/reports/wordstat-7-clusters-filled-2026-08-13.csv`.

## Добор

После сброса квоты:

```powershell
python scripts/wordstat_fetch_7_clusters.py --no-geo
```

## Топ RF (пока)

541 страховой стаж до 2002 · 479 архивная справка о стаже · 271 запрос в архив · 234 архивная справка для пенсии · 181 не засчитали стаж.
