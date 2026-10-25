# Закрытый журнал: production API-smoke `request-review` (2026-10-25)

**Классификация:** изменяющее действие в production (не read-only). Повторять без отдельного согласования **запрещено**. Записи **не** удалялись.

## Мета

| Поле | Значение |
|------|----------|
| Время job | `2026-10-25T06:15:42Z` → finished `06:15:43Z` |
| Инициатор | staff JWT (`requested_by` UUID `8feaeb93-…`, bootstrap-сессия admin) |
| Цель | synthetic case `d503add3-956a-48bc-91dc-1c3c3579e1a3` (`smoke-brief-*`) — без ПДн в публичном отчёте |
| Эндпоинт | `POST /api/portal/admin/cases/<id>/request-review` → api.proverkastaza.ru |
| Источник описания | отчёт исполнителя + `docs/ops/sfrfr-111-browser-api-smoke-2026-10-25.md` (ветка #269) |
| Backend SHA на момент smoke | **runtime `ef3fc44a`** (#273): deploy #277 ещё не был (`06:27Z`); #274 docs-only поверх того же кода |

## Job

| Поле | Значение |
|------|----------|
| job_id | `d11b298f-ede2-4533-b2a3-6d4c6580c7a1` |
| Итог | `status=needs_action`, `current_stage=done`, `attempts=1` |
| Предыдущий job на деле | `2b9ffa68-…` (2026-10-23), тоже `needs_action` |
| Результат дела | `pipeline_status=human_review`, `b2c_status=new`; в result есть `honest_brief` |

## Outbox / notify / заказы (read-only supabase2, 2026-10-25)

| Канал | Факт |
|-------|------|
| `case_chat_outbox` по case | **0** строк (sent/pending/всего) |
| `notification_jobs` по case | **0** |
| `orders` по case | **0** |
| Утверждение «live MAX не включался» | ручного включения нет; **авто-уведомлений по этому case после job также нет** (outbox/notify пусты). Это сильнее, чем «кнопку MAX не жали». |

## Ограничения доказательства

- Не browser E2E клик; UI primary при `needs_action` скрыт — отдельный функциональный пункт.
- Не доказательство кода #269: на VPS был **main/`ef3fc44a`**, не head #269.
- Не закрывает Auth-стенд A–G.
