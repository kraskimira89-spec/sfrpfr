# Playbook: автоматизация техдолга (ТЗ + Tracker)

**Дата:** 2026-09-22  
**Срез долга:** [tech-debt-2026-09-22.md](tech-debt-2026-09-22.md)  
**Статус:** канон ops

---

## 1. Цель

Максимум автоматизации **без** секретов Postbox/Supabase self-host:

1. Еженедельный снимок открытых задач Tracker → JSON.  
2. Напоминания-комментарии в FUNNEL / SFRFR.  
3. Создание недостающих задач SFRFR по P0 (идемпотентно по тегу).  
4. **Ensure досок** SFRFR / PUB / FUNNEL через Tracker Boards API.  
5. **Ensure Wiki-индекса** через Wiki API (soft-skip без `wiki:write`).  
6. Расписание на VPS рядом с реанимацией дел.

---

## 2. Что автоматизируем / что нет

| Можно авто | Нельзя / только owner |
|------------|------------------------|
| Snapshot JSON | Включение Postbox без ключей |
| Комментарии-напоминания | Self-host Supabase cutover |
| Ensure issues P0 | Ручной E2E MAX без тестового бота |
| **Доски SFRFR/PUB/FUNNEL (API)** | Тонкая настройка колонок/swimlane (опционально UI) |
| **Wiki-индекс (API + wiki:write)** | Без scope — soft-skip; выдать `wiki:write` или `WIKI_TOKEN` |

**Важно (проверено live 2026-09-22):** `POST /boards` на тарифе игнорирует name/queue
и запрещает `query` → код делает `POST` + сразу `PATCH` (имя, defaultQueue, filter).
Доски уже созданы: SFRFR `#4`, PUB `#5`, FUNNEL `#6`.
| Timer systemd | — |

Env:

- `TECH_DEBT_AUTO_COMMENT=1` (по умолчанию)
- `TECH_DEBT_ENSURE_BOARDS=1` (по умолчанию)
- `TECH_DEBT_ENSURE_WIKI=1` (по умолчанию; soft-skip при 401/403)
- `WIKI_SFRFR_SLUG=sfrfr` (опционально)
- `WIKI_TOKEN=…` (если у TRACKER_TOKEN нет scope wiki:write)

---

## 3. Расписание

| Когда | Что |
|-------|-----|
| **Пн 10:05 МСК** | `sfrfr tech-debt-due-tick` (snapshot + ensure issues + **boards/wiki** + comments) |
| Пн–Пт 10:15 МСК | `case-reactivation-due-tick` (уже есть) |

---

## 4. Команды

```bash
# План без записи в Tracker/Wiki
sfrfr tech-debt-due-tick --dry-run

# Тик: snapshot + ensure issues + boards/wiki + комментарии
sfrfr tech-debt-due-tick

# Только snapshot в файл
sfrfr tech-debt-due-tick --snapshot-only
```

Маркер идемпотентности в комментариях: `<!-- sfrfr-tech-debt-tick:YYYY-MM-DD -->`  
Повторный тик в ту же ISO-неделю не дублирует комментарий.

При **создании** доски/Wiki тик один раз комментирует seed (SFRFR-3, PUB-5, FUNNEL-4, SFRFR-5).

---

## 5. Ensure issues (P0)

Тег `tech-debt-auto` + уникальный `tech-debt:<id>`:

| id | Очередь | Тема |
|----|---------|------|
| `tz13-ingest-acceptance` | SFRFR | Закрыть/вычеркнуть чеклист приёмки ТЗ-13 |
| `tz09-e2e-parity` | SFRFR | Ручной E2E паритет MAX↔кабинет (ТЗ-09) |
| `tz15-supabase-cutover` | SFRFR | Решение срока self-host Supabase (ТЗ-15) |
| `tz31-postbox-prod` | SFRFR | уже есть SFRFR-40 — не дублировать |

---

## 6. VPS

Units: `docs/systemd/sfrfr-tech-debt.service` + `.timer`  
Ставятся из `scripts/vps_deploy.sh`.

Секреты Tracker на VPS: те же `TRACKER_*`. Для Wiki — `WIKI_TOKEN` при необходимости.

---

## 7. Критерии готовности

- [x] CLI + unit-тесты  
- [x] Timer в репо + install в deploy  
- [x] План в этом playbook  
- [x] Первый тик: ensure SFRFR-52/53/54 + комментарии FUNNEL/SFRFR (2026-W39)  
- [x] Timer active на VPS (после PR #23)  
- [ ] Ensure boards/wiki в тике (этот релиз)
