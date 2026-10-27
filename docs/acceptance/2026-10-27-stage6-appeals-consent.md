# Приёмка этапа 6: согласование первичных обращений

**Дата:** 2026-10-27  
**Скоуп:** ступень `appeals_consent` (после закрытого этапа 5). Ступени 7–8, клиентский UI согласия, этап 5 — вне скоупа.

## Что сделано

| Проверка | Ожидание | Результат |
|---|---|---|
| После `full_analysis_approved` | `appeals.need=recommended`, ступень 6 `needs_action` без consent | unit `case-funnel.test.ts` PASS |
| `appeals_consent_accepted` | ступень 6 `done` | unit PASS |
| ACCOMP 5000 без accepted | API 400 «Сначала зафиксируйте согласие…» | гейт в `create_order` + helper |
| ACCOMP 5000 / SUPPORT / DIAG | гейт только DOCS (ACCOMP≤6500), не SUPPORT/DIAG | unit `test_message_dedupe` PASS |
| Admin кнопка счёта 5 000 ₽ | disabled пока consent ≠ accepted + подсказка | UI |
| MAX `offer:appeals` | audit `appeals_consent_accepted`, затем DOCS | unit `test_max_bot_owned` PASS |
| MAX `offer:docs_skip` | без `appeals_consent_declined` | код |
| Этап 5 | не менялся | без правок full_analysis |

## Команды

```text
npx tsx --test src/lib/case-funnel.test.ts   # apps/admin
.\.venv\Scripts\python.exe -m pytest tests/unit/test_message_dedupe.py tests/unit/test_max_bot_owned.py -q
```

## Границы

- Клиентский кабинет: отдельного экрана согласия нет (staff / MAX CTA).
- Оплата и пакет обращений (ступени 7–8) — только гейт входа.
