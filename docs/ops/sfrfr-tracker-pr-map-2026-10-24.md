# Трекер ↔ PR (live MCP, цикл 5)

Источник: MCP `user-yandex-tracker` `issues_find` ~2026-10-24T16:40Z UTC.  
Не путать с более ранним документальным срезом.

## Live-статусы

| Тикет | Live | Фокус / остаток цикла 5 |
|---|---|---|
| SFRFR-111 | Открыт | Родитель; не закрывать |
| SFRFR-112 | Открыт | Контракт vs реализация |
| SFRFR-113 | Открыт | Browser UI login — блокер GoTrue; enqueue PostgREST есть |
| SFRFR-114 | Открыт | PostgREST claim/finalize доказан; полный extract E2E UI — нет |
| SFRFR-115 | Открыт | Gates/каталог в order path |
| SFRFR-116 | Открыт | `precheck:order` → DIAG; sandbox; не закрывать без browser+live |
| SFRFR-117 | Открыт | Сквозная приёмка; browser таблица пуста |

SFRFR-100 / SFRFR-110 — открыты (отдельный паспорт / DoD), не смешивать.

## Артефакты

- Checkpoint: `docs/ops/sfrfr-111-precheck-cycle5-checkpoint.md`
- Order evidence: `docs/ops/sfrfr-111-precheck-cycle5-order-e2e-evidence.md`
- PostgREST tests: `tests/integration/test_precheck_job_postgrest.py`
- PR #269 Auto-merge OFF
