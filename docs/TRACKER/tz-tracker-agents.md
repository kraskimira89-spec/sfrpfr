# ТЗ: Яндекс Трекер для агентов SFRFR

**Дата:** 2026-08-23  
**Очереди:** `SFRFR` · `PUB` · `FUNNEL`  
**MCP:** namespace `user-yandex-tracker` / сервер `yandex-tracker`

## 1. Цель

Сделать Трекер **единым бэклогом** продукта, публикаций и ops по воронке клиентов так, чтобы агенты Cursor:

1. создавали issues в **нужной очереди**;
2. комментировали прогресс;
3. переводили статусы (Open → In Progress → Done);
4. не клали ПДн и секреты в Трекер/Wiki.

## 2. Роли систем

| Задача | SoT |
|--------|-----|
| Продукт, infra, баги, lifecycle агентов | **SFRFR** |
| Публикации контента | **PUB** |
| Ops по этапам воронки (без ПДн) | **FUNNEL** |
| Wiki / оглавление | **Яндекс Wiki** (раздел SFRFR) |
| CRM по лиду/сделке | **amoCRM** |
| Код, ТЗ, канон | **git** |
| ПДн и дела клиентов | **Supabase + кабинеты** |

Notion в процесс **не** входит.

## 3. Три очереди (канон)

| Очередь | URL | Назначение |
|---------|-----|------------|
| **SFRFR** | https://tracker.yandex.ru/SFRFR | Продукт, деплой, infra, доска/Wiki, agent-lifecycle |
| **PUB** | https://tracker.yandex.ru/PUB | Слоты MAX / VK / blog / SEO / Директ |
| **FUNNEL** | https://tracker.yandex.ru/FUNNEL | Ops по этапам воронки; CRM детали — в amo |

Очередь org. **`TRACKER`** — не для продуктовых задач.

Создание очередей: `scripts/create_yandex_tracker_queues.py` (идемпотентно; перенос seed из SFRFR).

### Теги внутри очередей

**PUB** — один канал на задачу: `publish-max`, `publish-vk`, `publish-blog`, `publish-seo`, `publish-direct`.

**FUNNEL** — этап: `funnel-lead` … `funnel-loss` (см. playbook).

**SFRFR** — `ops`, `tracker`, `agents`, `infra`, `marketing` по смыслу.

Подробности: [playbook-publish-queue.md](playbook-publish-queue.md), [playbook-funnel-ops.md](playbook-funnel-ops.md).

## 4. Доска и Wiki (UI)

MCP **не** создаёт доски и Wiki. Чеклист: [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md).

Три доски (по одной на очередь) + Wiki-индекс SFRFR.

## 5. Цикл агента (обязательный)

См. [playbook-agent-task-lifecycle.md](playbook-agent-task-lifecycle.md).

Выбор очереди:

- фича/фикс/деплой → **SFRFR**
- пост/статья/слот → **PUB**
- SLA этапа, чеклист воронки, LOSS → **FUNNEL**

## 6. P0 / P1

| Приоритет | Примеры |
|-----------|---------|
| P0 | Падение деплоя, утечка ПДн |
| P1 | Доски трёх очередей, Wiki, слоты PUB на неделю, ops FUNNEL |
| P2 | Шаблоны, метрики |

## 7. ПДн и секреты

**Можно:** `case_id`, канал, этап, UTM, ссылки на `docs/`, commit SHA.

**Нельзя:** ФИО, телефон, email, СНИЛС, сканы, токены, пароли.

Секреты: `secrets/yandex-tracker.env`.

## 8. Seed-задачи (2026-08-23)

| Очередь | Ключи |
|---------|--------|
| SFRFR | SFRFR-3 (доска), SFRFR-4 (agents), SFRFR-5 (Wiki) |
| PUB | PUB-1 (эпик), PUB-2…4 (шаблоны), PUB-5 (доска) |
| FUNNEL | FUNNEL-1 (эпик), FUNNEL-2…3 (ops), FUNNEL-4 (доска) |

## 9. Связанные документы

- Ops: [../ops/yandex-tracker-ops.md](../ops/yandex-tracker-ops.md)
- Greenfield: [../ops/yandex-tracker-greenfield-checklist.md](../ops/yandex-tracker-greenfield-checklist.md)
- amo: [../AMO/playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md)
