# 2026-10-25 — срез «Мой маршрут / Собираем документы»

## Изменённые файлы

- `docs/specs/35-client-case-route.md` — маппинг глав + таблица источников + gaps
- `docs/specs/README.md`
- `apps/cabinet/src/lib/case-route.ts` (+ `.test.ts`) — главы, CTA, события, kit; явная ветка `upload` + нейтральный unknown CTA
- `apps/cabinet/src/components/case-route-panel.tsx`
- `apps/cabinet/src/components/case-work-map.tsx`
- `apps/cabinet/src/components/client-cabinet.tsx` — `cabinet-case-layout`: маршрут слева, чат справа
- `apps/cabinet/src/app/globals.css` — desktop ≥960px две колонки, sticky chat
- `apps/cabinet/src/app/dev/route-preview/*` — React preview `CaseWorkMap` + `ClientCaseChatPanel`
- `apps/cabinet/next.config.ts` — `allowedDevOrigins` для локального preview
- `apps/cabinet/tsconfig.json` (exclude `*.test.ts`)
- `src/sfrfr/services/client_work_map.py` — названия глав + мягкие статусы документов
- `tests/unit/test_client_work_map.py`
- `tools/client-route-preview/` — HTML-макет устарел (см. README)

## Исправления до приёмки (после review)

1. Блок переименован в **«Добавленные документы»**: только «Вы добавили документ…», без выдачи `added_at` за дату принятия/замены.
2. `resolveRoutePrimaryAction(cta_key)` — без fallback на upload; `unavailable` с понятным текстом.
3. Подсказки «Где получить» / «Не могу получить документ» только при `cta_key === upload`.
4. Для договора — `consequenceHint` с суммой из `order.amount_rub`.
5. В `nextStepFromWork()` — явная ветка `upload`; неизвестный CTA без документных подсказок + тест.
6. Desktop: чат остаётся справа от ленты этапов; помощь/`#case-chat-input` фокусирует тот же правый чат.

## Тесты / сборка

- `pytest tests/unit/test_client_work_map.py` — 19 passed
- `npx tsx --test apps/cabinet/src/lib/case-route.test.ts` — 12 passed (в т.ч. unknown CTA)
- `npx tsc --noEmit` в `apps/cabinet` — ok (CI)

## React preview (канон приёмки)

```text
cd apps/cabinet
npx next dev -p 3011
# http://localhost:3011/dev/route-preview?s=upload
```

Не путать с `tools/client-route-preview/index.html` (макет без React).
Узкая панель редактора ≠ размер кабинета: для приёмки задавать viewport **1440** и **390**.

### Layout + ширина чата

- Контейнер `CabinetCaseLayout`: колонки `main | splitter | chat` (≥960px).
- Автоширина: `--case-chat-width: clamp(320px, 38vw, 520px)`; сайт `width:100%`.
- Ручная подгонка: разделитель «Изменить ширину чата» (drag), двойной щелчок — сброс; значение в `localStorage`.
- Sticky-чат, лента скроллится внутри, composer снизу.

### Измерение CDP

| Viewport | layout | grid |
|---|---|---|
| 1440×900 | `side-by-side` | `~835px 10px 520px` |
| 390×844 | `stacked` | `1fr` |

### Проверка обработчиков (журнал preview, не toast HTML)

| Сценарий | resolve | handler |
|---|---|---|
| consent | `{"kind":"consent"}` | `handler: consent` |
| upload | `{"kind":"upload","slotKey":"ils"}` | `handler: upload slot=ils …` |
| contract | `{"kind":"contract"}` | `handler: contract` |
| pay | `{"kind":"pay","orderId":"ord-preview-1"}` | `handler: pay ord-preview-1` |
| result | `{"kind":"result","documentId":"doc-result-1"}` | `handler: result doc-result-1` |
| unknown | `unavailable` | skip без документных подсказок |
| unavailable | `unavailable` | skip |

### Скриншоты приёмки (размер области кабинета, не окна редактора)

`docs/history/assets/pr284-route-preview/`

| Файл | Содержание |
|---|---|
| `acceptance-desktop-1440.png` | **1440×900**, badge `layout=side-by-side`, маршрут+чат |
| `acceptance-mobile-390.png` | **390×844**, badge `layout=stacked` |
| `desktop-upload-route-chat.png` | Earlier desktop React preview |
| `phone-upload-stacked.png` | Earlier phone |

## Admin-чат: повторы (отдельно)

См. `docs/history/2026-10-25-admin-chat-repeat-probe.md` — в БД нет одного body×10; несколько system/client rows. История не трогалась, проверочные сообщения клиенту не слались. Не блокирует #284.

## Не на production

PR **без** auto-merge. Имя специалиста, контрольная дата и полная лента — вне этого PR.
Production не менялся этим срезом до явной приёмки.
