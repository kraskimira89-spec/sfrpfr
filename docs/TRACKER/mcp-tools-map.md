# Карта MCP Яндекс Трекер ↔ действия агента

**Namespace:** `user-yandex-tracker`

## Очереди

| Очередь | Когда |
|---------|--------|
| `SFRFR` | продукт, infra, agents |
| `PUB` | публикации |
| `FUNNEL` | ops воронки |

Поиск: `issues_find` с `"Queue": "PUB"` (YQL).

Создание очередей PUB/FUNNEL: `scripts/create_yandex_tracker_queues.py`.

## Issues (ключевое)

| Действие | Инструмент |
|----------|------------|
| Найти | `issues_find`, `issues_count` |
| Создать | `issue_create` (`queue` = SFRFR \| PUB \| FUNNEL) |
| Комментарий / статус | `issue_add_comment`, `issue_execute_transition`, `issue_close` |
| Перенос | `issue_move` (редко; лучше сразу в нужную очередь) |

## Не умеет MCP

- Доски и Wiki → [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md)
- Создать очередь → скрипт `create_yandex_tracker_queues.py` или API UI

## Примеры create

```text
# Публикация
queue: PUB
tags: ["publish-max", "marketing"]

# Воронка ops
queue: FUNNEL
tags: ["funnel-qualify", "ops"]

# Продукт
queue: SFRFR
tags: ["ops", "infra"]
```
