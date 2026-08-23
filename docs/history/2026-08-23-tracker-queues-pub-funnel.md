# 2026-08-23 — отдельные очереди PUB и FUNNEL

## Зачем

Публикации и ops воронки — в своих очередях Трекера, не в SFRFR.

## Сделано

- API: очереди **PUB**, **FUNNEL** (`scripts/create_yandex_tracker_queues.py`).
- Перенос seed: SFRFR-6→PUB-1, SFRFR-8…10→PUB-2…4, SFRFR-7→FUNNEL-1, SFRFR-11…12→FUNNEL-2…3.
- Новые: PUB-5 (доска PUB), FUNNEL-4 (доска FUNNEL).
- Доки `docs/TRACKER/`, ops, cursor rule — три очереди.

## Канон

| Очередь | URL |
|---------|-----|
| SFRFR | https://tracker.yandex.ru/SFRFR |
| PUB | https://tracker.yandex.ru/PUB |
| FUNNEL | https://tracker.yandex.ru/FUNNEL |
