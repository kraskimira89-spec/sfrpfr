# Этап 5: фоновый режим DRY_RUN=0 (старт)

## Включение

- `FISCAL_RECONCILE_DRY_RUN=0` (ENABLED=1, ALERT_SINCE без изменений)
- timer **enabled/active**
- Первый tick: `candidates=0`, `stale_alerts=0` (окно пустое после этапа 4)

## Наблюдение 24ч

Каждые 2 ч: время проверки UTC, timer/service, `ticks_last_2h` (≥1 = планировщик жив),
candidates/stale/ERROR/алерты. Стоп: второй чек / claimed_but_not_delivered / no_chat_id /
streak≥12 у неизвестного.

Live включён: **2026-10-23T21:01:27Z** → полные 24ч до **2026-10-24T21:01:27Z**
(= 25 окт 02:01:27 +05). Loop 12 ≈ в ту же отметку; если раньше — добить наблюдение до неё.
SFRFR-93/97 **не** закрывать только по candidates=0 — сверить критерии реализации и тесты.
Итог после финала: (1) стабильность 24ч (2) этап 4 (3) новые кандидаты/исходы.

## Снимок старта 2026-10-23T21:01Z

- dry_run=false, candidates=0 — OK

## Снимок 2026-10-23T23:01Z (loop #1 / 12, ~2 ч live)

- Timer каждые 10 мин: `dry_run=false`, **candidates=0**, stale=0
- ERROR / claimed_but_not_delivered / no_chat_id: нет
- `.env`: ENABLED=1 DRY_RUN=0; timer active

## Снимок 2026-10-24T01:01Z (loop #2 / 12, ~4 ч live)

- Тики 03:21–04:01 MSK: candidates=0, stale=0
- ERROR / алертов: нет

## Снимок 2026-10-24T03:01Z (loop #3 / 12, ~6 ч live)

- Тики до 06:01 MSK: candidates=0, stale=0
- ERROR / алертов: нет

## Interim 2026-10-24T03:47–03:53Z (между loop 3 и 4)

| Поле | Значение |
|------|----------|
| check_at_utc | 2026-10-24T03:52:57Z |
| timer | enabled / active |
| LAST tick | 06:51:27 MSK |
| ticks_last_2h | **12** |
| candidates / stale | 0 / 0 |
| error_lines_last_2h | 0 |
| новых кандидатов | нет |

## Снимок 2026-10-24T05:01:45Z (loop #4 / 12, ~8 ч live)

| Поле | Значение |
|------|----------|
| timer | enabled / active |
| LAST tick | 08:01:27 MSK |
| ticks_last_2h | **12** |
| candidates / stale | 0 / 0 |
| error_lines_last_2h | 0 |
| новых кандидатов | нет |
