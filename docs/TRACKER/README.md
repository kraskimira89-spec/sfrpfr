# TRACKER — пакет агента Яндекс Трекер

Рабочая папка чата Cursor про **Яндекс Трекер** для «Проверки стажа» (SFRFR).

## Очереди

| Очередь | Назначение |
|---------|------------|
| **STAZH** | https://tracker.yandex.ru/STAZH — качество, SLA, улучшения (из admin) |
| **SFRFR** | https://tracker.yandex.ru/SFRFR — продукт, infra, agents |
| **PUB** | https://tracker.yandex.ru/PUB — публикации |
| **FUNNEL** | https://tracker.yandex.ru/FUNNEL — ops воронки (без ПДн) |

Очередь org. `TRACKER` — **не** для продукта.

MVP кабинет → STAZH: [../ops/yandex-tracker-stazh-quality.md](../ops/yandex-tracker-stazh-quality.md)

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
| [plugin-sfrfr-issue-wizard.md](plugin-sfrfr-issue-wizard.md) | Weavix: мастер SFRFR / PUB / FUNNEL |
| [plugin-stazh-quality-wizard.md](plugin-stazh-quality-wizard.md) | Weavix: качество → **STAZH** |
| [reports/report-customer-tracker-plugins-2026-08-23.md](reports/report-customer-tracker-plugins-2026-08-23.md) | Отчёт заказчику по плагинам (23.08.2026) |

Скрипт очередей: `scripts/create_yandex_tracker_queues.py`.

## Жёсткие границы

- Без ПДн в issues/Wiki; CRM по клиенту — **кабинет сотрудника** ([../ops/playbook-staff-cabinet-crm.md](../ops/playbook-staff-cabinet-crm.md)); amo — резерв (`docs/AMO/`).
- Токен Tracker — только `secrets/yandex-tracker.env`.

## Плагины Weavix (статус 02.09.2026)

- **Мастер задач SFRFR** и **Качество STAZH** — `PUBLISHED` / `APPROVED`, в org. См. [plugin docs](plugin-sfrfr-issue-wizard.md), [отчёт](reports/report-customer-tracker-plugins-2026-08-23.md).
- STAZH-1/2/4: smoke/approve закрыты — [../ops/checklist-stazh-prod-smoke.md](../ops/checklist-stazh-prod-smoke.md).

## Полезное

- Тест владельца с одного MAX без лида в amo: [../ops/checklist-max-owner-test-no-amo.md](../ops/checklist-max-owner-test-no-amo.md)
