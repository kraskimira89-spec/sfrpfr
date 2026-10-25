# 2026-10-25 — срез «Мой маршрут / Собираем документы»

## Изменённые файлы

- `docs/specs/35-client-case-route.md` — маппинг глав + таблица источников + gaps
- `docs/specs/README.md`
- `apps/cabinet/src/lib/case-route.ts` (+ `.test.ts`) — главы, CTA, события, kit
- `apps/cabinet/src/components/case-route-panel.tsx`
- `apps/cabinet/src/components/case-work-map.tsx`
- `apps/cabinet/src/components/client-cabinet.tsx`
- `apps/cabinet/src/app/globals.css`
- `apps/cabinet/tsconfig.json` (exclude `*.test.ts`)
- `src/sfrfr/services/client_work_map.py` — названия глав + мягкие статусы документов
- `tests/unit/test_client_work_map.py`
- `tools/client-route-preview/index.html` — изолированный preview до merge

## Исправления до приёмки (после review)

1. Блок переименован в **«Добавленные документы»**: только «Вы добавили документ…», без выдачи `added_at` за дату принятия/замены.
2. `resolveRoutePrimaryAction(cta_key)` — без fallback на upload; `unavailable` с понятным текстом.
3. Подсказки «Где получить» / «Не могу получить документ» только при `cta_key === upload`.
4. Для договора — `consequenceHint` с суммой из `order.amount_rub`.

## Тесты / сборка

- `pytest tests/unit/test_client_work_map.py` — 19 passed
- `node --experimental-strip-types --test apps/cabinet/src/lib/case-route.test.ts` — 11 passed
- `npx tsc --noEmit` в `apps/cabinet` — ok

## Preview и скриншоты (до merge)

Локально: `python -m http.server 8765 --directory tools/client-route-preview` → `http://127.0.0.1:8765/`

Скриншоты: `docs/history/assets/pr284-route-preview/`

| Файл | Сценарий |
|---|---|
| `desktop-consent.png` | Согласие → CTA consent, без документных подсказок |
| `desktop-upload.png` | Недостающий ИЛС |
| `desktop-waiting.png` | Комплект передан, ждёт специалиста |
| `desktop-contract.png` | Договор + сумма 3 000 ₽ |
| `desktop-unavailable.png` | Результат без файла — недоступность CTA |
| `phone-upload.png` | Тот же upload на 390×844 |

## Не на production

PR **без** auto-merge. Production не менялся этим срезом до явной приёмки.
