# TRACKER — пакет агента Яндекс Трекер

Рабочая папка чата Cursor про **Яндекс Трекер** для «Проверки стажа» (SFRFR).

## Очереди

| Очередь | Назначение |
|---------|------------|
| **SFRFR** | https://tracker.yandex.ru/SFRFR — продукт, infra, agents |
| **PUB** | https://tracker.yandex.ru/PUB — публикации |
| **FUNNEL** | https://tracker.yandex.ru/FUNNEL — ops воронки (без ПДн) |

Очередь org. `TRACKER` — **не** для продукта.

## Быстрый старт

1. Новый чат Agent → **«TRACKER»**.
2. Промпт: [prompt-agent-tracker.md](prompt-agent-tracker.md).
3. Режим: SFRFR / PUB / FUNNEL / доски / Wiki.

## Файлы пакета

| Файл | Назначение |
|------|------------|
| [tz-tracker-agents.md](tz-tracker-agents.md) | Полное ТЗ |
| [prompt-agent-tracker.md](prompt-agent-tracker.md) | Промпт чата |
| [playbook-agent-task-lifecycle.md](playbook-agent-task-lifecycle.md) | Lifecycle MCP |
| [playbook-publish-queue.md](playbook-publish-queue.md) | Очередь **PUB** |
| [playbook-funnel-ops.md](playbook-funnel-ops.md) | Очередь **FUNNEL** |
| [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md) | Доски + Wiki (UI) |
| [mcp-tools-map.md](mcp-tools-map.md) | Карта MCP |

Скрипт очередей: `scripts/create_yandex_tracker_queues.py`.

## Жёсткие границы

- Без ПДн в issues/Wiki; CRM — amo.
- Токен Tracker — только `secrets/yandex-tracker.env`.
