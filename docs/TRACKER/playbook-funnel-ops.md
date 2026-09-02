# Playbook: ops-задачи по воронке клиентов

**Очередь Трекера:** **`FUNNEL`** → https://tracker.yandex.ru/FUNNEL  
**CRM по людям:** **кабинет сотрудника** ([playbook-staff-cabinet-crm.md](../ops/playbook-staff-cabinet-crm.md)). amoCRM в резерв (`AMOCRM_ENABLED=0`, `docs/AMO/`).

## Назначение

Внутренние задачи: SLA этапа, чеклисты, баг sync колонки, LOSS_REASON в UI — **без** карточек с ПДн.

## Теги этапов

| Тег | Смысл |
|-----|--------|
| `funnel-lead` | новый лид |
| `funnel-qualify` | квалификация |
| `funnel-diag` | диагностика / 3k |
| `funnel-docs` | документы в кабинете |
| `funnel-submit` | клиент подаёт сам |
| `funnel-result` | ожидание СФР |
| `funnel-review` | отзыв |
| `funnel-loss` | отказ / LOSS |

Канон этапов и смысла продаж: [../AMO/playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md), [../marketing-sales/playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md).

Ops-фокус FUNNEL: SLA первого ответа (цель 30–60 мин в рабочие часы), обязательность next step в процессе, LOSS_REASON, узкие места «не прислали ИЛС / боятся цену / не дошли до оплаты».

**Playbook'и (staff cabinet):**

| Задача | Документ |
|--------|----------|
| FUNNEL-2 SLA | [../ops/playbook-funnel-lead-sla.md](../ops/playbook-funnel-lead-sla.md) |
| FUNNEL-5 clarity | [../ops/playbook-funnel-clarity-dialog-review.md](../ops/playbook-funnel-clarity-dialog-review.md) · [../marketing-sales/playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md) |
| Оператор | [../ops/playbook-staff-new-lead-cheatsheet.md](../ops/playbook-staff-new-lead-cheatsheet.md) |
| Доска FUNNEL | [ops-board-wiki-checklist.md](ops-board-wiki-checklist.md) § FUNNEL-4 |

## Шаблон

**queue:** `FUNNEL`

**Summary:** `Проверить SLA на этапе qualify` (префикс `[FUNNEL]` опционален).

В description: этап, `case_id` только если нужен (без ФИО/телефона).

## Граница staff cabinet / FUNNEL

| Кабинет сотрудника | FUNNEL (Трекер) |
|--------------------|-----------------|
| дело, этап, next_action, loss_reason | системные ops, SLA, чеклисты, улучшения процесса |

amo (резерв): исторические чеклисты — [../AMO/playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md).
