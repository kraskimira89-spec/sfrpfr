# ТЗ: Яндекс Трекер для агентов SFRFR

**Дата:** 2026-08-23  
**Очередь:** `SFRFR` (https://tracker.yandex.ru/SFRFR)  
**MCP:** namespace `user-yandex-tracker` / сервер `yandex-tracker`

## 1. Цель

Сделать Трекер **единым бэклогом** продукта, ops, публикаций и внутренних задач по воронке клиентов так, чтобы агенты Cursor:

1. находили и создавали issues в `SFRFR`;
2. комментировали прогресс;
3. переводили статусы (Open → In Progress → Done);
4. не клали ПДн и секреты в Трекер/Wiki.

## 2. Роли систем

| Задача | SoT |
|--------|-----|
| Задачи, баги, публикации, ops-воронка | **Яндекс Трекер** (`SFRFR`) |
| Wiki / оглавление для команды без git | **Яндекс Wiki** (раздел SFRFR) |
| CRM по лиду/сделке | **amoCRM** (`docs/AMO/`) |
| Код, ТЗ, канон копирайта | **git** `docs/`, `src/` |
| ПДн и дела клиентов | **Supabase + кабинеты** |

Notion в процесс **не** входит.

## 3. Одна очередь, «логические очереди» тегами

Отдельные очереди `PUB` / `FUNNEL` **не** создаём. Всё в `SFRFR`:

| Поток | Префикс summary | Теги |
|-------|-----------------|------|
| Продукт / infra / agents | `[OPS]` / без | `ops`, `tracker`, `agents`, `infra` |
| Публикации | `[PUB]` | `publish-max`, `publish-vk`, `publish-blog`, `publish-seo`, `publish-direct` |
| Воронка (ops) | `[FUNNEL]` | `funnel-lead` … `funnel-loss` (см. playbook) |

Доски в UI: общая + фильтры по тегам Publish / Funnel.

Подробности: [playbook-publish-queue.md](playbook-publish-queue.md), [playbook-funnel-ops.md](playbook-funnel-ops.md).

## 4. Доска и Wiki (UI)

MCP **не** создаёт доски и Wiki. Владелец/агент выполняет чеклист: [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md).

Минимум колонок: **Open → In Progress → Done**.

Wiki: оглавление + ссылки на `docs/TRACKER/`, `docs/ops/`, `docs/AMO/`, `docs/marketing-sales/` — без копирования секретов и ПДн.

## 5. Цикл агента (обязательный)

См. [playbook-agent-task-lifecycle.md](playbook-agent-task-lifecycle.md) и [mcp-tools-map.md](mcp-tools-map.md).

Кратко:

1. `issues_find` — нет ли уже задачи.
2. `issue_create` в `SFRFR` с тегами.
3. `issue_execute_transition` → In Progress при старте работы.
4. `issue_add_comment` по итогам (пути файлов, PR/commit, без секретов).
5. переход в Done / Closed.

## 6. P0 / P1

| Приоритет | Примеры |
|-----------|---------|
| P0 | Падение деплоя, сломан sync лида, утечка ПДн в публичный канал |
| P1 | Доска/Wiki, lifecycle агентов, очередь публикаций на неделю, ops-задачи воронки (SLA/чеклисты) |
| P2 | Улучшения Wiki, шаблоны, метрики |

## 7. ПДн и секреты

**Можно:** `case_id`, канал (web/MAX/VK), этап воронки, UTM-метки гипотез, ссылки на `docs/`, commit SHA.

**Нельзя:** ФИО, телефон, email, СНИЛС, сканы, тексты документов клиента, токены (`y0_…`, OAuth), пароли.

Секреты Tracker: только `secrets/yandex-tracker.env` (см. [../ops/yandex-tracker-mcp.md](../ops/yandex-tracker-mcp.md)).

## 8. Критерии готовности пакета

- [x] Самодостаточное ТЗ в этом файле.
- [x] Промпт + playbook’и + cursor rule в репо.
- [x] В `SFRFR` заведены задачи: доска (SFRFR-3), Wiki (SFRFR-5), agent-lifecycle (SFRFR-4), эпики PUBLISH (SFRFR-6) и FUNNEL (SFRFR-7) + шаблоны.
- [x] Smoke SFRFR-2 прокомментирован и закрыт (fixed).
- [x] Коммит + push без секретов.

## 9. Связанные документы

- Ops: [../ops/yandex-tracker-ops.md](../ops/yandex-tracker-ops.md)
- Greenfield: [../ops/yandex-tracker-greenfield-checklist.md](../ops/yandex-tracker-greenfield-checklist.md)
- amo воронка: [../AMO/playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md)
- Подача: `scripts/assets/copy/submission-position.md`
