# 2026-09-08 — Дашборд: экран очереди по карточкам

## Зачем

Клик по метрикам дашборда только фильтровал таблицу на том же экране. Фильтр «Конфликты каналов» считал почти все дела с выбранным каналом (`channel !== unset`), а счётчик на карточке — только prefer MAX/web без привязки.

## Что сделано

- Backend: `build_work_item` отдаёт `max_linked`, `web_linked`, `channel_conflict`, `conflict_kind`, `conflict_detail`; дашборд считает конфликты через `channel_link_flags`.
- Frontend: `view=queue` + `?queue=new|docs|conflicts|…`; компонент `dashboard-queue-panel` — рекомендации + список + суть конфликта.
- Фильтр conflicts: только `channel_conflict === true`.
- Deep-link `?queue=` после логина (рядом с `?case=`).

## Критерий

Число на карточке ≈ число строк в очереди; у конфликтов виден текст «предпочтение MAX, MAX не привязан» (или web) и действие сотруднику.
