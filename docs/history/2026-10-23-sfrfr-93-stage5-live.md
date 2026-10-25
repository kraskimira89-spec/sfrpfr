# Этап 5: фоновый режим DRY_RUN=0 — финал 24ч

Live-окно: **2026-10-23T21:01:27Z** → **2026-10-24T21:01:27Z**.  
Проверка финала: **2026-10-24T21:02:19Z** (после отметки 24ч).

## Env / timer (VPS)

| Поле | Значение |
|------|----------|
| `FISCAL_RECONCILE_ENABLED` | `1` |
| `FISCAL_RECONCILE_DRY_RUN` | `0` |
| `FISCAL_RECONCILE_ALERT_SINCE` | `2026-10-23T17:47:35Z` |
| timer | `enabled` / `active` (каждые 10 мин) |

## 1. Стабильность (за 24ч с 21:01Z)

| Метрика | Значение |
|---------|----------|
| Тики timer (Starting / Finished / JSON `enabled`) | **144** (ровно 24ч × 6/ч) |
| Ранее ошибочно «162» | артефакт `journalctl --since` без UTC/`--until` (MSK ≈ +18) — см. control-point |
| `claimed_but_not_delivered` | 0 |
| `no_chat_id` | 0 |
| Traceback | 0 |
| `error_before_post` | 7 (только кандидат `89be641d` до исключения) |
| `gate_succeeded` в journal live | 0 |
| Тики с `candidates` ≥ 1 | были в раннем окне; после исключения — 0 |

Stop-conditions за окно **не срабатывали**. Timer продолжает работать в фоне.  
**Число тиков ≠ доказательство отсутствия дублей чеков.**

## 2. Доказательство этапа 4 (create vs gate)

| Событие | Итог |
|---------|------|
| CLI `yookassa-retry-receipt` `d41bd2ce` (этап 4) | `gate_succeeded` — существующий `type=payment` чек; **новый POST create не создавался** |
| Повтор CLI на том же id | снова `gate_succeeded` |
| Live 24ч | **нет** живого create-пути (новый чек через reconcile) |

Вывод: идемпотентный gate / skip доказан; **путь «создать новый чек при canceled» в live не подтверждён** (кандидатов с create не было).

## 3. Новые кандидаты

| Период | Кандидаты |
|--------|-----------|
| Раннее окно | `89be641d` (`provider_payment_id` = `receipt:…`) → `error_before_post`, streak до исключения; затем `fiscal_status=not_required` |
| После исключения → финал | `candidates=0`, `stale_alerts=0` на каждом тике |
| На финале (21:02Z) | manual tick: `{"candidates": 0, "stale_alerts": 0, "results": []}` |

Пустое окно **не** доказывает create-путь.

## Критерии Tracker (без авто-закрытия)

### SFRFR-93

| Критерий | Статус |
|----------|--------|
| Job опрашивает paid без succeeded/pending | ✅ код + live |
| Повтор только через `ensure_payment_receipt` / gate | ✅ |
| Тесты webhook/двойной тик/succeeded no-op | ✅ через этап 1 / SFRFR-97 |
| Документ `docs/yookassa-setup.md` | ✅ |
| Live create при `reg=canceled` | ⏳ не было кандидата |

**Не закрывать** только из‑за `candidates=0`.

### SFRFR-97

Unit-матрица 1–28 / прогон 95 — см. таблицу покрытия.  
**Группа B (live) не закрыта** этапом 5 → задачу **не** закрывать по этому отчёту.  
Сверка DoD: `docs/history/2026-10-25-sfrfr-97-dod-reconcile.md`.

## Решение контрольной точки (2026-10-25)

SFRFR-93 **open** до естественного create. Конфиг не менять.  
Журнал: `docs/history/2026-10-25-sfrfr-93-stage5-control-point.md`.

## Loop-лог (кратко)

- #8: `89be641d` → streak → `not_required`
- #11 (19:02Z): green, candidates=0
- #12 (21:02Z): green, 24ч закрыты → этот отчёт
