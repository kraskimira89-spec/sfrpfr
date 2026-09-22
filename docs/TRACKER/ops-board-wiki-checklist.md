# Чеклист: доски и Wiki

**Обновление 2026-09-22:** доски и Wiki-индекс создаются **через API** в weekly tick
(`sfrfr tech-debt-due-tick` → `TECH_DEBT_ENSURE_BOARDS=1`, `TECH_DEBT_ENSURE_WIKI=1`).
MCP по-прежнему **не** создаёт доски; ручной UI — только fallback / тонкая настройка колонок.

Канон авто: [../ops/playbook-tech-debt-automation.md](../ops/playbook-tech-debt-automation.md).

## Доска SFRFR (авто)

- Имя / очередь: `SFRFR` · board id **4** · https://tracker.yandex.ru/SFRFR/agile/4
- Seed: [SFRFR-3](https://tracker.yandex.ru/SFRFR-3) — закрывать после комментария «Авто: доска создана»

Ручной fallback: https://tracker.yandex.ru/SFRFR → Доски → колонки Open / In Progress / Done.

## Доска PUB (авто)

- Имя / очередь: `PUB` · board id **5** · https://tracker.yandex.ru/PUB/agile/5
- Seed: [PUB-5](https://tracker.yandex.ru/PUB-5)

Опционально вручную: колонки Backlog → Draft → Ready → Published.

## Доска FUNNEL (авто)

- Имя / очередь: `FUNNEL` · board id **6** · https://tracker.yandex.ru/FUNNEL/agile/6
- Seed: [FUNNEL-4](https://tracker.yandex.ru/FUNNEL-4) — скрин **не** обязателен, если есть авто-комментарий API

Опционально вручную (вариант B): swimlane по тегам `funnel-*` —
см. [playbook-funnel-ops.md](playbook-funnel-ops.md).

## Wiki SFRFR (авто)

- Slug по умолчанию: `sfrfr` (override: `WIKI_SFRFR_SLUG`)
- Нужен OAuth scope **wiki:write** — тот же `TRACKER_TOKEN` или отдельный `WIKI_TOKEN`
- Seed: [SFRFR-5](https://tracker.yandex.ru/SFRFR-5)
- Без Notion, без ПДн

При 401/403 тик делает soft-skip и пишет hint в лог/stats — UI не блокирует.

## Seed-задачи

| Задача | Что |
|--------|-----|
| SFRFR-3 | доска SFRFR |
| PUB-5 | доска PUB |
| FUNNEL-4 | доска FUNNEL |
| SFRFR-5 | Wiki-индекс |

## Техдолг (срез)

[../ops/tech-debt-2026-09-22.md](../ops/tech-debt-2026-09-22.md) ·
[../ops/playbook-tech-debt-automation.md](../ops/playbook-tech-debt-automation.md)

## Создание очередей PUB/FUNNEL

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/create_yandex_tracker_queues.py
```

Идемпотентно: создаёт PUB/FUNNEL при отсутствии; переносит seed из SFRFR.
