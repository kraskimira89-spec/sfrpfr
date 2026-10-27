# Приёмка ступени 10: контроль рассмотрения

**Дата:** 2026-10-27
**Код:** `case_follow_up_events` + `POST …/follow-up-control`; дата = `cases.next_action_at`

## Критерии

| # | Проверка | Результат |
|---|---|---|
| 1 | После ступени 9 контроль без автосрока | unit + derive |
| 2 | Дата/ответственный сохраняются | next_action_at + expert_user_id |
| 3 | Перенос сохраняет историю и причину | events.reschedule |
| 4 | Просрочка = overdue_internal, не «СФР отказал» | UI label |
| 5 | Idempotency не дублирует | service |
| 6 | Файл не ответ без handoff | response_handoff |
| 7 | Live: assign → check → reschedule → handoff на `1579e69f-…` | **PASS** (#358 deploy) |

Календарь контроля: `Asia/Yekaterinburg` (UTC+5).
