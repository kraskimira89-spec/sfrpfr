# Приёмка ступени 9 (форма): клиент + сотрудник

**Дата:** 2026-10-27
**Код:** таблица `case_submission_reports`, `POST …/submission` (admin+client), UI cabinet/admin

## Критерии

| # | Проверка | Результат |
|---|---|---|
| 1 | Передача пакета ≠ завершение этапа 9 | unit + derive |
| 2 | Клиент сохраняет с полями; proof необязателен | API + cabinet UI |
| 3 | Повторный клик / idempotency_key не дублирует | service |
| 4 | Help ≠ подача | kind help_requested |
| 5 | Автор, время, source, package_version в report | serialize |
| 6 | Staff source = Со слов клиента | validate |
| 7 | Live: staff form + idempotent replay; client POST `client_self` | **PASS** на `1579e69f-…` после #356 deploy |

## Handoff ступени 10

После `client_reported`: `followUp.state=active`, `submittedOn` в facts; контрольная дата только вручную.
