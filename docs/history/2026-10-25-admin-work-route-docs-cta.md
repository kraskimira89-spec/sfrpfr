# 2026-10-25 — Левый маршрут «Работа с делом» (admin)

## Цель

В кабинете сотрудника под таблицей документов снова доступны: кнопка проверки,
краткое резюме после успеха, действия «спросить клиента» / счёт DIAG 3000 /
PDF анализа после оплаты; обращение 5000 — отдельный этап без автосоздания.

## Что сделано

- SoT `case_work_route.py`: без файлов → `request_docs_from_client`; `needs_action` → `request_docs_check`.
- `CaseWorkRoute`: primary по `route.primary_action`; панель проверки на `current|done|blocked`; fallback «Проверить документы».
- `DocumentCheckPanel`: шаблоны в чат, счёт DIAG, отправка ссылки, upload PDF после оплаты; подсказка про ACCOMP 5000.
- `admin-cabinet`: `createQuickOrder` для быстрого DIAG.

## Проверено

- `pytest tests/unit/test_case_work_route.py` — 4 passed.
- `npx tsc --noEmit` в `apps/admin` — ok.

## Вне скоупа

Клиентский маршрут / PR 284; авто-MAX; новые тарифы.
