# Трекер ↔ PR (live MCP + docs, 2026-10-24 вечер)

Источник статусов: MCP `user-yandex-tracker` `issues_find` / `issue_get`  
(не только сохранённая карта). Время среза: ~2026-10-24T16:18Z UTC.

## Live-статусы предпроверки

| Тикет | Статус (live) | Assignee | PR / остаток |
|---|---|---|---|
| SFRFR-100 | Открыт | не назначен* | Паспорт; не смешивать с precheck |
| SFRFR-110 | Открыт | не назначен* | DoD / E01-wire / границы записи |
| SFRFR-111 | Открыт | пуст (`issue_get`) | #269; изоляция+лог cycle5; PostgREST/browser открыты |
| SFRFR-112 | Открыт | не назначен* | Ревью контракта/артефактов |
| SFRFR-113 | Открыт | не назначен* | reclaim есть; browser/restart остаток |
| SFRFR-114 | Открыт | не назначен* | PG suite; PostgREST-путь остаток |
| SFRFR-115 | Открыт | не назначен* | каталог/отказ |
| SFRFR-116 | Открыт | не назначен* | callback wire; полный order/pay |
| SFRFR-117 | Открыт | не назначен* | сквозная приёмка |

\*В выдаче `issues_find` поле assignee отсутствовало → трактуем как незаполненное; для SFRFR-111 подтверждено `issue_get` без assignee.

## Артефакты cycle 5

- Канон сырой лог: `docs/ops/logs/sfrfr-111-isolation-pytest-20261024-212031-afbe33de.txt` (**77 passed**, SHA `afbe33de…`)
- Evidence: `docs/ops/sfrfr-111-precheck-isolation-cycle5-evidence.md`

## Открытые PR

| PR | Связь | Действие |
|---|---|---|
| #269 | precheck | Auto-merge OFF; без merge/deploy |
| #268 | date-op | параллельно |
| #41 / #42 | OCR/HITL docs | не deps |

## Правила

- Hardening ≠ закрытие тикетов.
- Карта обновляется после live MCP; не подменять live срезом из старого md без повторного запроса.
