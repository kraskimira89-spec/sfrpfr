# Этап 5: фоновый режим DRY_RUN=0 (старт)

## Включение

- `FISCAL_RECONCILE_DRY_RUN=0` (ENABLED=1, ALERT_SINCE без изменений)
- timer **enabled/active**
- Первый tick: `candidates=0`, `stale_alerts=0` (окно пустое после этапа 4)

## Наблюдение 24ч

Каждые 2 ч: journal + candidates; стоп при втором чеке / claimed_but_not_delivered / streak≥12 у неизвестного.

## Снимок старта 2026-10-23T21:01Z

- dry_run=false, candidates=0 — OK
