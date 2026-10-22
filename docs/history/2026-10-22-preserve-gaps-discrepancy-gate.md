# 2026-10-22: preserve_gaps не ставит discrepancy без prior soft-ask/brief

## Проблема

В `preserve_gaps_after_soft_ask_yes` после #203 `DISCREPANCY_KEY=1` выставлялся всегда, а analysis-флаги (`STATUS_COMPLETED`, summary, revive) — только при `prior_soft or had_brief`. Холодный клик `diag:detail_yes` оставлял несогласованное состояние: gaps «есть», completed — нет.

## Исправление

Ранний `return`, если нет prior soft-ask и нет prior brief. `DISCREPANCY_KEY` / `SOFT_ASK_SENT_KEY` / revive и completed поднимаются только вместе.

Тест: `test_preserve_without_prior_soft_ask_does_not_invent_completed`.
