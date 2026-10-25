# 2026-10-25 — срез «Мой маршрут / Собираем документы»

## Изменённые файлы

- `docs/specs/35-client-case-route.md` — маппинг глав + таблица источников + gaps
- `docs/specs/README.md`
- `apps/cabinet/src/lib/case-route.ts` (+ `.test.ts`)
- `apps/cabinet/src/components/case-route-panel.tsx`
- `apps/cabinet/src/components/case-work-map.tsx`
- `apps/cabinet/src/components/client-cabinet.tsx`
- `apps/cabinet/src/app/globals.css`
- `apps/cabinet/tsconfig.json` (exclude `*.test.ts`)
- `src/sfrfr/services/client_work_map.py` — названия глав + мягкие статусы документов
- `tests/unit/test_client_work_map.py`

## Тесты / сборка

- `pytest tests/unit/test_client_work_map.py` — 19 passed
- `node --experimental-strip-types --test apps/cabinet/src/lib/case-route.test.ts` — 4 passed
- `npx tsc --noEmit` в `apps/cabinet` — ok

## Скриншоты

Не сняты в этой сессии: нужен вход в клиентский кабинет с тестовым делом.  
После merge/preview — телефон + desktop на главе «Собираем документы» (3 сценария из ТЗ).

## Не на production

PR **без** auto-merge. Экран не объявляется доступным на проде до ручной приёмки.
