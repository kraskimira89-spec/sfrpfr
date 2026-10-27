# Приёмка ступени 9: подтверждение подачи

**Дата:** 2026-10-27
**Код:** POST `/api/portal/admin/cases/{id}/submission` → audit `submission_confirmed` | `submission_help_requested`

## Ожидание

| Проверка | Результат |
|---|---|
| `appeals_package_delivered` без confirm → `awaiting_client` / waiting | unit PASS |
| `submission_confirmed` → stage done | unit PASS |
| `submission_help_requested` → needs_action | unit PASS |
| Передача пакета ≠ подача; копирайт «подаёте сами / решает СФР» | UI |
| Live: confirm на деле после delivered | после deploy |

## Вне скоупа

Этапы 5–8 не меняем. Follow-up / ответ СФР / SUPPORT 8000 — отдельно.
