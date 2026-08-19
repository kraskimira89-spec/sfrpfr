# AMO — пакет агента amoCRM

Рабочая папка чата Cursor про **amoCRM** для «Проверки стажа» (SFRFR).

## Быстрый старт

1. Новый чат Agent → имя **«AMO»** / **«amoCRM»**.
2. Скопировать блок из [prompt-agent-amocrm.md](prompt-agent-amocrm.md).
3. При необходимости уточнить: настройка / sync / воронка / E2E-проверка.

## Файлы пакета

| Файл | Назначение |
|------|------------|
| [prompt-agent-amocrm.md](prompt-agent-amocrm.md) | **Промпт** для нового чата |
| [how-we-work-amocrm.md](how-we-work-amocrm.md) | Как работаем с amoCRM (роли систем, поток, день оператора) |
| [role-amocrm.md](role-amocrm.md) | Роль агента и границы |
| [tz-12-amocrm.md](tz-12-amocrm.md) | ТЗ-12: интеграция (продукт / код) |
| [ops-amocrm-setup.md](ops-amocrm-setup.md) | Пошаговая настройка UI + env |
| [qa-lead-amocrm-e2e.md](qa-lead-amocrm-e2e.md) | QA: лид WP → API → amo |
| [sales-pipeline-amocrm.md](sales-pipeline-amocrm.md) | Воронка продаж, LOSS, поля атрибуции (из foundation) |
| [playbook-funnel-checklists-automation.md](playbook-funnel-checklists-automation.md) | Этапы, чеклисты, SLA, авто, маппинг SFRFR→amo |
| [playbook-operator-amo-card.md](playbook-operator-amo-card.md) | Что видит оператор в карточке: поля + перечень документов без содержимого |
| [playbook-operator-new-lead-cheatsheet.md](playbook-operator-new-lead-cheatsheet.md) | **Шпаргалка на 1 стр.** (новый лид) + [PDF](assets/playbook-operator-new-lead-cheatsheet.pdf) |
| [ops-amocrm-task-templates.md](ops-amocrm-task-templates.md) | Шаблоны задач amo (Digital Pipeline + тексты из кода) |
| [vendor-user-docs.md](vendor-user-docs.md) | Оглавление пользовательской доки amo |
| [vendor-dev-docs.md](vendor-dev-docs.md) | Оглавление доки разработчика amo |

## Канон в репозитории (не ломать ссылки)

При правках содержимого ТЗ обновлять **и** копию здесь, **и** оригинал:

- Продуктовое ТЗ: `docs/specs/12-amocrm.md`
- Ops: `docs/ops/amocrm-setup.md`
- QA: `docs/qa/lead-amocrm-e2e.md`
- Код: `src/sfrfr/integrations/amocrm/`
- Маркетинг / CRM-поля: `docs/marketing-sales/spec-marketing-sales-foundation.md` §9

## Жёсткие границы

- В amo **нет** сканов, СНИЛС, ИЛС, OCR, Storage URL.
- Источник истины по делу — SFRFR (Supabase + кабинет).
- Токен `AMO_ACCESS_TOKEN` — только в `secrets/` и `/opt/sfrfr/.env`, не в git.
- Канон подачи: `scripts/assets/copy/submission-position.md`.
