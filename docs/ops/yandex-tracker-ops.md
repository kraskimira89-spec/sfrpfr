# Яндекс Трекер + Wiki + amo: зелёный старт (без Notion)

**Дата:** 2026-08-22  
**Контекст:** внутренние задачи и wiki — в контуре Яндекс 360; Notion **не** мигрируем, всё заводим с нуля.

## Роли инструментов

| Задача | SoT | MCP / доступ |
|--------|-----|----------------|
| Продукт, infra, баги, agents | **SFRFR** | [yandex-tracker-mcp.md](./yandex-tracker-mcp.md) |
| Публикации контента | **PUB** | то же |
| Ops воронки (без ПДн) | **FUNNEL** | то же |
| Wiki, playbooks, оглавление | **Яндекс Wiki** (раздел SFRFR) | UI; критичное дублируем в `docs/` git |
| CRM-заметки по лиду/сделке | **amoCRM** | [`docs/AMO/`](../AMO/README.md) |
| Код, ТЗ, контракты | **git** `docs/` | Cursor + репозиторий |
| ПДн клиентов, дела | **Supabase YC** | приложение SFRFR |

## Notion

- **Не** переносим страницы и базы из Notion.
- Plugin `notion-workspace` в Cursor — **выключен** (см. [`.cursor/settings.json`](../../.cursor/settings.json)).
- Старый Notion MCP — не использовать; при необходимости архив только вне рабочего процесса.

## Трекер: минимальная настройка (UI, один раз)

1. Организация: Яндекс 360 или Yandex Cloud (org id — в `secrets/yandex-tracker.env`).
2. Очереди (2026-08-23):
   - **`SFRFR`** — продукт и ops: https://tracker.yandex.ru/SFRFR
   - **`PUB`** — публикации: https://tracker.yandex.ru/PUB
   - **`FUNNEL`** — воронка ops: https://tracker.yandex.ru/FUNNEL  
   Создание: `python scripts/create_yandex_tracker_queues.py` (клон `issueTypesConfig` с SFRFR).
3. Типы **Task**, **Веха** (workflow quickStartV2PresetWorkflow).
4. Доски **SFRFR**, **PUB**, **FUNNEL** — Open → In Progress → Done (PUB: можно Backlog/Draft/Ready/Published).
5. Компоненты/метки: `marketing`, `ops`, `legal`, `infra`; в PUB — `publish-*`; в FUNNEL — `funnel-*`.

## Wiki

1. Раздел **SFRFR** — оглавление (ссылки на `docs/marketing-sales/`, `docs/ops/`, ТЗ).
2. Не копировать Notion; новые страницы пишем в Wiki или сразу в git `docs/`.
3. Playbook’и каноничны в репо; Wiki — для команды без git.

## amoCRM

- Заметки по клиенту/лиду — **только** в amo (сделка/контакт).
- В Трекер и Wiki **не** кладём ФИО, телефон, email, СНИЛС, номера дел клиентов.

## ПДн и 152-ФЗ

| Можно в Трекер/Wiki | Нельзя |
|---------------------|--------|
| внутренние задачи, маркетинг, infra | ФИО/телефон/email клиента |
| ссылки на `case_id` без ПДн | тексты документов клиента |
| UTM, гипотезы, чеклисты | пароли, ключи API |

## Связанные документы

- Пакет агента: [../TRACKER/README.md](../TRACKER/README.md) · [../TRACKER/tz-tracker-agents.md](../TRACKER/tz-tracker-agents.md)
- MCP: [yandex-tracker-mcp.md](./yandex-tracker-mcp.md)
- Чеклист: [yandex-tracker-greenfield-checklist.md](./yandex-tracker-greenfield-checklist.md)
- amo: [../AMO/README.md](../AMO/README.md)
- DataLens / dbt: [datalens-management-bi.md](./datalens-management-bi.md)
- Supabase YC: [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md)
