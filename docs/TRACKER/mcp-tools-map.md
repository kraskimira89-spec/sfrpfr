# Карта MCP Яндекс Трекер ↔ действия агента

**Namespace:** `user-yandex-tracker`  
**Очередь по умолчанию:** `SFRFR`

Перед вызовом уточнять схему через GetDynamicTools при сомнении в параметрах.

## Issues

| Действие агента | Инструмент |
|-----------------|------------|
| Найти задачи (YQL / очередь) | `issues_find`, `issues_count` |
| Прочитать задачу | `issue_get` |
| Создать задачу | `issue_create` (`queue=SFRFR`, `summary`, `description`, `tags`, `type`, `priority`, `parent`) |
| Обновить поля | `issue_update` |
| Комментарий | `issue_add_comment`, `issue_update_comment`, `issue_delete_comment` |
| Список комментариев | `issue_get_comments` |
| Вложения / чеклист / worklog | `issue_get_attachments`, `issue_get_checklist`, `issue_get_worklogs`, `issue_add_worklog`, … |
| Связи | `issue_get_links`, `issue_add_link`, `issue_delete_link` |
| История | `issue_get_changelog` |
| URL задачи | `issue_get_url` |
| Закрыть / сменить статус | `issue_get_transitions` → `issue_execute_transition`; либо `issue_close` |
| Переместить | `issue_move` |

## Очередь и справочники

| Действие | Инструмент |
|----------|------------|
| Список очередей | `queues_get_all` |
| Метаданные / компоненты / версии | `queue_get_metadata`, `queue_get_tags`, `queue_get_versions`, `queue_get_fields` |
| Типы / приоритеты / статусы / резолюции | `get_issue_types`, `get_priorities`, `get_statuses`, `get_resolutions` |
| Шаблоны issues | `issue_templates_get_all`, `issue_template_get` |
| Глобальные поля | `get_global_fields` |

## Пользователи

| Действие | Инструмент |
|----------|------------|
| Текущий | `user_get_current` |
| Поиск | `users_search`, `users_get_all`, `user_get` |

## Не умеет MCP (делать в UI)

- Создать **доску** и колонки → [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md)
- Создать страницы **Wiki** → тот же чеклист
- OAuth / org id → `secrets/yandex-tracker.env` + [../ops/yandex-tracker-mcp.md](../ops/yandex-tracker-mcp.md)

## Рекомендуемый минимальный сценарий

1. `issues_find` — дубли?
2. `issue_create` с тегами (`ops` / `publish-*` / `funnel-*`)
3. `issue_get_transitions` + `issue_execute_transition` → In Progress
4. Работа в репо / UI
5. `issue_add_comment` + переход в Done
6. Для smoke: комментарий в SFRFR-2

## Пример create (логика)

```text
queue: SFRFR
summary: [OPS] …
description: markdown, без ПДн
type: task
priority: normal
tags: ["ops", "tracker"]
```
