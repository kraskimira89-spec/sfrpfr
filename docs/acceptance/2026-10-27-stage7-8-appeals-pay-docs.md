# Приёмка ступеней 7–8: оплата и пакет первичных обращений

**Дата:** 2026-10-27  
**Перед этим:** регрессия этапа 5 — `docs/acceptance/2026-10-27-stage5-regression-before-78.md` (PASS).

## Ступень 7 `appeals_payment`

| Проверка | Ожидание | Результат |
|---|---|---|
| Согласие, без счёта | `not_started` | unit PASS |
| ACCOMP 5000 pending | `waiting` | unit PASS |
| ACCOMP 5000 paid | `done`, entitlement granted | unit PASS |
| Повторный счёт | кнопка disabled при открытом/оплаченном 5k | UI |
| Без этапа 6 | кнопка disabled (гейт этапа 6) | уже в #348 |

## Ступень 8 `appeals_documents`

| Проверка | Ожидание | Результат |
|---|---|---|
| Черновик без ready | `working` / in_progress | unit PASS |
| `appeals_package_ready` | ready, needs_action | unit PASS |
| `appeals_package_delivered` | done | unit PASS |
| API `POST .../appeals-package` | audit ready\|delivered | код |
| UI «Пакет готов» / «Передан клиенту» | пишет audit | admin |
| DOCX скачать | без изменений | уже было |

## Вне скоупа

SUPPORT 8000 / escalation; подтверждение подачи (ступень 9); клиентский кабинет самообслуживания.
