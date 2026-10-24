# Триаж открытого бэклога (агент, 2026-10-24)

Срез: Tracker `Queue: SFRFR AND Status: "Открыт"` → **44** задачи.  
Правило: выполнять код/docs/CI без поломки этапов; **не** live MAX / боевые платежи / удаление ВМ / закрытие 110–117 без DoD.

## A. В работе сейчас (агент)

| Ключ | Действие | Статус |
|---|---|---|
| SFRFR-111 / 112–117 | PR #269 isolation_guard + suite 83; CI green; Auto-merge **OFF** | код готов, приёмка browser/live открыта |
| SFRFR-110 стек | PR #261→#263→#266→#267 (цепочка base) — включать auto-merge по порядку | в очереди |
| SFRFR-100 / 256 | паспорт docs — auto-merge если CLEAN | docs |
| SFRFR-93 / 260 | exclude receipt_ocr — auto-merge при зелёном CI | фикс |
| SFRFR-97 | таблица 1–28 в #256; группа B (live create/MAX) — owner/стенд | не закрывать |
| SFRFR-270 | срез 1 — supersede #269 | закрыть PR |

## B. Owner / UI / live (агент не закрывает)

| Ключи | Почему |
|---|---|
| SFRFR-105, 107 | решения владельца / эксперт |
| SFRFR-101–104, 106 | E2E/prod/auth/backup протоколы |
| SFRFR-90–95, 98–99 | ЮKassa/Evotor/live pending |
| SFRFR-65 | удалить старую ВМ — destructive |
| SFRFR-3, 5 | доска/Wiki — owner UI Tracker |
| PUB/FUNNEL ops | операторский ритм |
| SFRFR-52–55, 40 | tech-debt / Postbox / MCP — отдельные ТЗ |

## C. Не смешивать

- SFRFR-110 DoD ≠ закрытие через precheck-111.
- Merge #269 до browser/live — **не** (запрет ТЗ + незакрытый DoD §12).
