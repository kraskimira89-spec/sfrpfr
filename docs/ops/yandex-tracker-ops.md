# Яндекс Трекер + Wiki + amo: зелёный старт (без Notion)

**Дата:** 2026-08-22  
**Контекст:** внутренние задачи и wiki — в контуре Яндекс 360; Notion **не** мигрируем, всё заводим с нуля.

## Роли инструментов

| Задача | SoT | MCP / доступ |
|--------|-----|----------------|
| Задачи, спринты, баги | **Яндекс Трекер** (очередь `SFRFR`) | [yandex-tracker-mcp.md](./yandex-tracker-mcp.md) |
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
2. Очередь **`SFRFR`** — основная для продукта и ops (создана 2026-08-23; https://tracker.yandex.ru/SFRFR).
   Через API нужны `lead` (trackerUid) и `issueTypesConfig` — скопировать с `TRACKER?expand=issueTypesConfig`.
3. Типы задач: минимум **Task**, **Bug** (при необходимости **Story**).
4. Доска **SFRFR** — колонки по умолчанию (Open → In Progress → Done).
5. Компоненты/метки по необходимости: `marketing`, `ops`, `legal`, `infra`.

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

- MCP: [yandex-tracker-mcp.md](./yandex-tracker-mcp.md)
- Чеклист: [yandex-tracker-greenfield-checklist.md](./yandex-tracker-greenfield-checklist.md)
- amo: [../AMO/README.md](../AMO/README.md)
- DataLens / dbt: [datalens-management-bi.md](./datalens-management-bi.md)
- Supabase YC: [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md)
