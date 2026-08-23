# Playbook: жизненный цикл задачи агента

**Очередь:** `SFRFR`  
**MCP:** `user-yandex-tracker`

## Цикл

```text
discover (issues_find)
  → create (issue_create) при отсутствии дубля
  → In Progress (issue_execute_transition)
  → comment (issue_add_comment) по итогам шагов
  → Done / Closed
```

## Когда создавать issue

- Новая фича / фикс / ops-работа с измеримым результатом.
- Публикация контента (см. [playbook-publish-queue.md](playbook-publish-queue.md)).
- Внутренняя ops-задача по этапу воронки (см. [playbook-funnel-ops.md](playbook-funnel-ops.md)).
- Баг, воспроизводимый без ПДн.

**Не** создавать дубль: сначала `issues_find` по ключевым словам / тегам.

## Шаблоны summary

| Тип | Пример |
|-----|--------|
| Ops / продукт | `[OPS] Доска SFRFR: колонки Open / In Progress / Done` |
| Агенты | `[AGENTS] Обязательный цикл задач через MCP` |
| Публикация | `[PUB] MAX: пост про северный стаж (слот YYYY-MM-DD)` |
| Воронка | `[FUNNEL] Проверить SLA ответа на этапе qualify` |
| Баг | `[BUG] Sync amo: status не обновляется после docs_in` |

## Теги (минимум)

- Всегда полезны: `ops` | `agents` | `tracker`
- Публикации: ровно один из `publish-*`
- Воронка: один из `funnel-*`
- Приоритет: `normal` по умолчанию; P0 — `critical` / явный текст в description

## Description (markdown)

1. Цель (1–2 предложения).
2. Контекст / ссылки на `docs/…` или commit.
3. Чеклист шагов.
4. Критерий Done.
5. Без ПДн и секретов.

## Комментарий при закрытии

Кратко: что сделано, пути файлов, ключ коммита/PR, что осталось владельцу (UI доска/Wiki и т.п.).

## Переходы статусов

Использовать `issue_get_transitions` → `issue_execute_transition`.  
Типичный путь: Open → In Progress → Done (имена статусов смотреть в очереди).
