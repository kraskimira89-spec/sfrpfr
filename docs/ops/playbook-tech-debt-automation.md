# Playbook: автоматизация техдолга (ТЗ + Tracker)

**Дата:** 2026-09-22  
**Срез долга:** [tech-debt-2026-09-22.md](tech-debt-2026-09-22.md)  
**Статус:** канон ops

---

## 1. Цель

Максимум того, что можно автоматизировать **без** owner UI (доски/Wiki) и **без** секретов Postbox/Supabase self-host:

1. Еженедельный снимок открытых задач Tracker → JSON.  
2. Напоминания-комментарии в FUNNEL / SFRFR (чеклисты, без закрытия задач).  
3. Создание недостающих задач SFRFR по P0 из среза (идемпотентно по тегу).  
4. Расписание на VPS рядом с реанимацией дел.

---

## 2. Что автоматизируем / что нет

| Можно авто | Нельзя / только owner |
|------------|------------------------|
| Snapshot JSON | Доски Tracker (SFRFR-3, PUB-5, FUNNEL-4) |
| Комментарии-напоминания | Wiki (SFRFR-5) |
| Ensure issues P0 | Включение Postbox без ключей |
| Timer systemd | Self-host Supabase cutover |
| Dry-run реанимации в отчёте | Ручной E2E MAX без тестового бота |

---

## 3. Расписание

| Когда | Что |
|-------|-----|
| **Пн 10:05 МСК** | `sfrfr tech-debt-due-tick` |
| Пн–Пт 10:15 МСК | `case-reactivation-due-tick` (уже есть) |

Env: `TECH_DEBT_AUTO_COMMENT=1` (по умолчанию на VPS).

---

## 4. Команды

```bash
# План без комментариев в Tracker
sfrfr tech-debt-due-tick --dry-run

# Тик: snapshot + ensure issues + комментарии
sfrfr tech-debt-due-tick

# Только snapshot в файл
sfrfr tech-debt-due-tick --snapshot-only
```

Маркер идемпотентности в комментариях: `<!-- sfrfr-tech-debt-tick:YYYY-MM-DD -->`  
Повторный тик в ту же ISO-неделю не дублирует комментарий.

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

Секреты Tracker на VPS: те же `TRACKER_*`, что для quality issues (в `/opt/sfrfr/.env` или `secrets/`).

---

## 7. Критерии готовности

- [x] CLI + unit-тесты  
- [x] Timer в репо + install в deploy  
- [x] План в этом playbook  
- [x] Первый тик: ensure SFRFR-52/53/54 + комментарии FUNNEL/SFRFR (2026-W39)  
- [ ] После merge: timer active на VPS
