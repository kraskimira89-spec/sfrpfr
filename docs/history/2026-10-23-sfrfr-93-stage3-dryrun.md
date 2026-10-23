# Этап 3: dry-run timer (старт)

## Env / timer (91.229.11.147)

- `FISCAL_RECONCILE_ENABLED=1`
- `FISCAL_RECONCILE_DRY_RUN=1`
- `FISCAL_RECONCILE_ALERT_SINCE=2026-10-23T17:47:35Z`
- timer: **enabled / active**, период **10 мин**

## Снимок 2026-10-23T17:54:25Z

- candidates=7 (после этапа 2)
- actions: `lease_busy` (lease 120 с после ручного tick)
- по 7 строкам окна: `attempts=0`, `streak=0`, `payload=false`, `alerted=false`, `outcome=NULL`, `leased=true`
- ERROR в journal: нет

## План наблюдения

Каждые ~30 мин ~3ч: journal + DB snapshot. Ожидание: только `last_reconcile_at` / lease, без attempts/streak/payload/alert.

## Снимок 2026-10-23T17:58:09Z

- Timer LAST `20:57:43` MSK: **7× `dry_run`**, candidates=7
- DB: attempts=0 streak=0 payload=false alerted=false outcome=NULL leased=true
- ERROR: нет
- Следующий тик timer ~10 мин

## Снимок 2026-10-23T18:25:01Z (loop #1 / 6)

- Timer тики 21:07 / 21:17 MSK: **7× `dry_run`** каждый
- DB: attempts=0 streak=0 payload=false alerted=false outcome=NULL
- ERROR: нет

## Снимок 2026-10-23T18:55:07Z (loop #2 / 6)

- Timer 21:27 / 21:37 / 21:47 MSK: **7× `dry_run`**
- DB: attempts/streak/payload/alert = 0 — без изменений
- ERROR: нет (~1 ч наблюдения)

## Снимок 2026-10-23T19:25:06Z (loop #3 / 6)

- Timer 21:57 / 22:07 / 22:17 MSK: **7× `dry_run`**
- DB: без изменений (только lease)
- ERROR: нет (~1.5 ч наблюдения)

## Снимок 2026-10-23T19:55:06Z (loop #4 / 6)

- Timer 22:27 / 22:37 / 22:47 MSK: **7× `dry_run`**
- DB: attempts/streak/payload/alert = 0
- ERROR: нет (~2 ч наблюдения)

## Снимок 2026-10-23T20:25:05Z (loop #5 / 6)

- Timer 22:57 / 23:07 / 23:17 MSK: **7× `dry_run`**
- DB: без изменений
- ERROR: нет (~2.5 ч наблюдения)

## Снимок 2026-10-23T20:55:05Z (loop #6 / 6) — этап 3 DONE

- Timer 23:27 / 23:37 / 23:47 MSK: **7× `dry_run`**
- ~3 ч: только lease; attempts/streak/payload/alert = 0; ERROR нет
- Вердикт: **этап 3 зелёный** → этап 4
