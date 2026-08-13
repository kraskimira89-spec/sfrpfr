# Playbook: дозаполнение Wordstat для 7 кластеров

Файл данных: [wordstat-7-clusters-template.csv](wordstat-7-clusters-template.csv)  
Research: [../research-seo-problem-clusters-wordstat-2026-08.md](../research-seo-problem-clusters-wordstat-2026-08.md)  
API setup: [../../ops/yandex-wordstat-setup.md](../../ops/yandex-wordstat-setup.md)

## Предпочтительно: API

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/wordstat_fetch_7_clusters.py          # TBD + гео
python scripts/wordstat_fetch_7_clusters.py --no-geo # TBD только РФ (экономия квоты)
```

Нужен `secrets/yandex-wordstat.env` (см. ops). Квота ~100 req/час.

## Запасной путь: веб UI

1. Открыть https://wordstat.yandex.ru/ → регион **Россия**.
2. Для каждой строки CSV с `freq_rf=TBD` вписать частотность.
3. Гео → колонка `freq_geo` как `Москва:123; СПб:45; ЯНАО:0; ХМАО:2`.
4. Сохранить копию `wordstat-7-clusters-filled-YYYY-MM-DD.csv`.

## Не делать

- Не коммитить `secrets/yandex-wordstat.env` и API-ключи.
- Не подставлять частоты «на глаз» как факты.
