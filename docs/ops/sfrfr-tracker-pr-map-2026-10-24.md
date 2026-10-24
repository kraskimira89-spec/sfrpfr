# Трекер ↔ PR (live MCP, после isolation_guard)

Источник: MCP Tracker + `gh pr` ~2026-10-24T17:00Z UTC.

## SFRFR-111

| Тикет | Live | Фокус |
|---|---|---|
| SFRFR-111 | Открыт | PR **#269** @ `65b6881a`; Auto-merge **OFF** |
| SFRFR-112–117 | Открыт | код готов; browser/live — остаток; **не закрывать** |

Evidence: `sfrfr-111-stage-progress.md`, `sfrfr-111-isolation-gate-report.md`, suite 83 passed.

PR **#270** (срез 1) — закрыт как superseded by #269.

## SFRFR-110 стек (цепочка base)

| PR | Base | Назначение | Auto-merge |
|---|---|---|---|
| #261 | main | dialogue quality | включён по очереди |
| #263 | #261 | E05/F04 wire | после #261 |
| #266 | #263 | LLM claim filter | после #263 |
| #267 | #266 | DoD matrix docs | после #266 |
| #265 | ? | period-date audit docs | отдельно |
| #268 | main | date correction | **BLOCKED** (fail check) — не трогать |

## Прочее

| PR | Тема | Примечание |
|---|---|---|
| #256 | SFRFR-100 passport | docs; rebase если behind |
| #260 | SFRFR-93 exclude receipt_ocr | фикс |
| #259 | SFRFR-84 evidence path | tests |

## Owner-blocked (не исполнять агентом)

SFRFR-105/107 решения; 101–104/106 E2E/prod/auth; 90–95/98–99 live ЮKassa; 65 удаление ВМ; 3/5 доски Wiki UI.

Карта triage: `docs/ops/open-backlog-agent-triage-2026-10-24.md`.
