# TRACKER — пакет агента Яндекс Трекер

Рабочая папка чата Cursor про **Яндекс Трекер** для «Проверки стажа» (SFRFR).

Очередь продукта/ops: **`SFRFR`** → https://tracker.yandex.ru/SFRFR  
Очередь `TRACKER` (орг. «Главное рабочее пространство») — **не** для продуктовых задач.

## Быстрый старт

1. Новый чат Agent → имя **«TRACKER»** / **«Трекер»**.
2. Скопировать блок из [prompt-agent-tracker.md](prompt-agent-tracker.md).
3. Уточнить режим: доска/Wiki / lifecycle агентов / публикации / воронка / seed задач.

## Файлы пакета

| Файл | Назначение |
|------|------------|
| [prompt-agent-tracker.md](prompt-agent-tracker.md) | **Промпт** для нового чата |
| [tz-tracker-agents.md](tz-tracker-agents.md) | Полное ТЗ: доска, Wiki, агенты, публикации, воронки |
| [playbook-agent-task-lifecycle.md](playbook-agent-task-lifecycle.md) | Жизненный цикл задачи агента через MCP |
| [playbook-publish-queue.md](playbook-publish-queue.md) | Очередь публикаций (теги `publish-*`) |
| [playbook-funnel-ops.md](playbook-funnel-ops.md) | Ops-задачи по воронке клиентов (теги `funnel-*`, без ПДн) |
| [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md) | UI: доска и Wiki |
| [mcp-tools-map.md](mcp-tools-map.md) | Карта MCP ↔ действия агента |

## Ops в репо (не дублировать секреты)

- [../ops/yandex-tracker-ops.md](../ops/yandex-tracker-ops.md) — роли систем
- [../ops/yandex-tracker-mcp.md](../ops/yandex-tracker-mcp.md) — MCP / env
- [../ops/yandex-tracker-greenfield-checklist.md](../ops/yandex-tracker-greenfield-checklist.md) — чеклист зелёного старта

## Связанные пакеты

- amoCRM (воронка продаж): [../AMO/](../AMO/README.md)
- VK (контент): [../VK/](../VK/README.md)
- Маркетинг: [../marketing-sales/](../marketing-sales/README.md)

## Жёсткие границы

- В issues и Wiki **нет** ФИО, телефонов, email клиентов, СНИЛС, сканов, текстов переписки с ПДн.
- CRM-заметки по лиду — только в **amo**; в Трекере — ops/продукт/публикации + `case_id` без ПДн.
- Токен Tracker — только `secrets/yandex-tracker.env`, не в git.
- Канон подачи: `scripts/assets/copy/submission-position.md`.
