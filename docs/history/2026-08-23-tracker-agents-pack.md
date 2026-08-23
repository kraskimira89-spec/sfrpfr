# 2026-08-23 — пакет docs/TRACKER + seed SFRFR

## Зачем

Агенты Cursor ведут бэклог в Яндекс Трекере (очередь `SFRFR`): доска, Wiki, lifecycle, очередь публикаций и ops по воронке без ПДн.

## Сделано

- Пакет `docs/TRACKER/` (README, ТЗ, промпт, playbook lifecycle / publish / funnel, board-wiki checklist, mcp-tools-map).
- Правило `.cursor/rules/tracker-folder.mdc`.
- Обновлены `docs/ops/yandex-tracker-greenfield-checklist.md`, ссылки в `yandex-tracker-ops.md`.
- Seed в Трекере: SFRFR-3…12; smoke SFRFR-2 закрыт (fixed).

## Не сделано через API

- UI доска и Wiki — чеклист владельцу (SFRFR-3, SFRFR-5).
