# Карта callback-путей MAX (SFRFR-110)

Инвентаризация по `handle_max_update` и связанным модулям (2026-10-24).
**Картирование ≠ исправление.** Правки — узкими задачами по подтверждённым дефектам.

Общий механизм повтора: `_is_rapid_repeat_callback` (~12 с) → `duplicate_payload_cooldown`
(прямой `_reply`, без бизнес-действия). Не покрывает все семантические повторы (оплата, offer).

Ответ по умолчанию у клиентских callback: **прямой** `_reply` / `bot.send_message`,
не E05/F04 outbox. Исключения: invoice/offer могут `enqueue_max_delivery`.

## Сводная таблица

| Префикс / payload | Точка входа | User/дело | Доверенное состояние | Повтор | Актуальность кнопки | Эффект | Send | Сбой | Тест / пробел |
|---|---|---|---|---|---|---|---|---|---|
| `start_dialog` | `handler` start_hit | max_user → case | consent evidence | cooldown | одноразовая по смыслу согласия | PDN consent + intake start | прямой | consent gate | unit intake; пробел: E-policy нет |
| `pdn_consent:no` | handler | max_user | decline flag | cooldown | да | отказ ПДн | прямой | — | consent tests; вне E05 |
| `confirm_web_login` / `confirm_web_login\|id` | login_hit | ticket | login_pending | cooldown | ticket status | подтверждение входа | прямой | resume pending | security tests |
| `approve_staff_login\|id` | manager_ticket | manager user | ticket | cooldown | ticket | approve staff | прямой | — | ops/security |
| `get_login_code` | login flow | max_user | — | cooldown | — | код/ссылка | прямой | — | login |
| `intake:*` | `_handle_intake_callback` | intake store + case | MaxIntakeRecord | cooldown | step FSM | смена шага анкеты | прямой | fallback menu | intake tests |
| `intake:callback` | operator/callback wait | intake | `_callback_wait` | cooldown | wait flag | запрос звонка | прямой + ops notify | — | callback contact |
| `q:*` | questionnaire_flow | intake active | q answers | cooldown | active q | ответ анкеты | прямой | — | q tests |
| `menu:upload/docs/status/operator` | `_handle_questionnaire_or_menu` | case_id | status resolve | cooldown | слабая | статус/меню | прямой | fallback text | status reply |
| `diag:*` | `diag_choice.handle` | case + brief gate | diag pending / offer gate | cooldown | `is_pending` + gate | счёт 3000 / checklist | прямой + invoice enqueue | FAIL_TEXT | diag_offer_gate |
| `lm:*` | `checklist_offer.handle` | intake | lm active | cooldown | is_active | чек-лист / email | прямой | — | checklist tests |
| `offer:docs/appeals/support/docs_skip` | `handle_offer_callback` | case_id required | tariff gates | cooldown; skip path | gate evaluate | счёт / отказ offer | enqueue + иногда прямой | skip reply | invoice gates; **вне E05** |
| `llmsoft:*` | remap → offer/intake/text | soft label | — | cooldown | устаревание soft | перемаршрутизация | см. цель | — | **актуальность soft слабая** |
| `max:doc:done` | doc_bg final | case docs | docs_seen | cooldown | docs state | итог комплекта | прямой | incomplete text | doc_bg |
| `max:doc:type:*` / `max:doc:confirm:*` | `document_type_flow` | case | intake | cooldown | legacy confirm | тип документа | прямой | staff ping best-effort | doc_type; legacy |
| `svy:*` | `survey_flow` | user_id | survey state | cooldown | — | опрос ясности | прямой | — | survey; вне E05 |
| `review:*` | `review_flow` | user_id | review state | cooldown | — | отзыв/оценка | прямой | — | review; вне E05 |
| marketing / СТОП | `_handle_marketing_consent` | user | consent flags | cooldown | — | opt-out | прямой | — | marketing |
| ops drafts / site review | `ops_bot.handle_ops_update` | ops bot | draft ids | отдельный бот | — | публикация | ops send | — | **не клиентский AI** |

## Поля (шаблон для дозаполнения при дефекте)

```text
Путь / назначение:
Файл::функция:
Кто вызывает:
Проверка пользователя и дела:
Доверенный источник состояния:
Защита от повторного нажатия:
Актуальность кнопки:
Действие и внешние эффекты:
Outbox или прямой send:
Поведение при сбое:
Тест:
Пробел:
Связанная задача:
```

## Закрытость карты

- [x] Префиксы из `handle_max_update` перечислены
- [x] Связанные модули `diag` / `lm` / `q` / `intake` / `offer` / `doc` / `svy` / `review` / login
- [x] Построчный разбор основных `intake:*` / `q:*` subcodes — см. `sfrfr-110-max-callback-intake-q-subcodes.md`
- [ ] Полный граф helper-переходов `_continue_after_*` (не payload)
- [ ] Ops-only callbacks вне клиентского контура — отдельный реестр
- [ ] Повторный grep после merge #261/#263

Карта **достаточна для приоритизации**, не «закрыта на 100% helper-графа».  
E05/F04 на callback **не** распространяется.

## Подтверждённые пробелы (не чинить в этом PR)

1. Soft-кнопки `llmsoft:` без жёсткой проверки актуальности offer.
2. Большинство callback → прямой send, минуя outbox stages / E-policy.
3. Cooldown ≠ идемпотентность финансовых offer.
4. Legacy `max:doc:confirm:*` ещё жив.
