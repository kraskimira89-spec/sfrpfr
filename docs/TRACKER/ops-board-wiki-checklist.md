# Чеклист UI: доски и Wiki

MCP **не** создаёт доски и Wiki.

## Доска SFRFR

1. https://tracker.yandex.ru/SFRFR → Доски.
2. Колонки: **Open → In Progress → Done**.
3. Задачи продукта, infra, agents.

## Доска PUB

1. https://tracker.yandex.ru/PUB → Доски.
2. Колонки: **Backlog → Draft → Ready → Published** (или Open/In Progress/Done).
3. Фильтр по тегам `publish-*` при необходимости.

## Доска FUNNEL

1. https://tracker.yandex.ru/FUNNEL → Доски.
2. Колонки Open/In Progress/Done или по этапам + теги `funnel-*`.

## Wiki SFRFR

1. Раздел **SFRFR** в Яндекс Wiki.
2. Индекс: `docs/TRACKER/`, `docs/ops/`, `docs/AMO/`, `docs/marketing-sales/`, `docs/VK/`.
3. Без Notion, без ПДн.

## Seed-задачи на доски

- SFRFR-3 — доска SFRFR
- PUB-5 — доска PUB
- FUNNEL-4 — доска FUNNEL
- SFRFR-5 — Wiki

## Создание очередей PUB/FUNNEL

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/create_yandex_tracker_queues.py
```

Идемпотентно: создаёт PUB/FUNNEL при отсутствии; переносит seed из SFRFR.
