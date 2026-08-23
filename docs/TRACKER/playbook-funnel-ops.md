# Playbook: ops-задачи по воронке клиентов

**Очередь Трекера:** **`FUNNEL`** → https://tracker.yandex.ru/FUNNEL  
**CRM по людям:** только **amoCRM** (`docs/AMO/`).

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

Канон этапов amo: [../AMO/playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md).

## Шаблон

**queue:** `FUNNEL`

**Summary:** `Проверить SLA на этапе qualify` (префикс `[FUNNEL]` опционален).

В description: этап, `case_id` только если нужен (без ФИО/телефона).

## Граница с amo

| amo | FUNNEL |
|-----|--------|
| сделка, контакт, задачи оператора | системные ops, улучшения SLA, баги sync |
