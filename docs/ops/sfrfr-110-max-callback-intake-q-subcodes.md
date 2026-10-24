# Callback subcodes: `intake:*` и `q:*`

Дополнение к `sfrfr-110-max-callback-coverage.md`. Разбор FSM-переходов
по коду `handler._handle_intake_callback` и `questionnaire.apply_answer`
(SHA базы аудита: `4bb8c0d7…`).

Общее: повтор — `_is_rapid_repeat_callback` (~12 с); ответ — прямой `_reply`;
E05/F04 не применяется. Доступ: `max_user_id` → intake/case; отдельной
проверки «чужое дело» на каждый subcode нет сверх привязки intake.

## `intake:*` (состояние: `MaxIntakeRecord` в intake store)

| Payload | Изменение состояния | Внешний эффект | Актуальность | Пробел |
|---|---|---|---|---|
| `intake:restart` | `restart(user)` | welcome + whom KB | всегда | сброс без confirm |
| `intake:callback` / `intake:operator` / `intake:goal:operator` | goal=operator при goal | `_handle_operator` | cooldown | ops notify вне E |
| `intake:docs_info` | — | текст docs + KB | — | info only |
| `intake:docs:base\|stazh\|special\|gosuslugi\|missing\|ils_howto` | — | раздел docs | — | info only |
| `intake:back` | откат полей по `step()` | предыдущий вопрос | зависит от step | много веток |
| `intake:whom:self\|relative` | for_whom; сброс ниже | pension Q | FSM | — |
| `intake:pension:before\|assigned` | pension_status | problem Q | FSM | — |
| `intake:problem:ils_stazh\|north\|documents\|sfr_refusal` | problem_type + goal sync | ils Q | FSM | — |
| `intake:goal:check_experience\|missing_period\|sfr_question\|operator` | legacy goal | next after goal | legacy | старые кнопки |
| `intake:ils:yes\|no\|unknown\|need` | ils_available; howto flags | howto или continue | FSM | — |
| `intake:ils_guide:done\|mfc` | ils_howto_done / текст МФЦ | continue / info | FSM | — |
| `intake:emp:yes\|partial\|no` | employment_records_available | next / howto | FSM | — |
| `intake:emp_guide:done` | emp_howto_done | continue | FSM | — |
| `intake:device:max\|web\|help` | device_preference | summary / help | FSM; кабинет=сайт | legacy labels |

`файл::функция`: `integrations/max/handler.py::_handle_intake_callback`  
Клавиатуры: `integrations/max/intake.py` (payload builders).

**Остаток:** текстовые ответы на шагах waiting (не callback) и полная матрица
`_ask_next_after_goal` / `_continue_after_ils` — отдельные ветки без новых payload.

## `q:*` и menu (анкета ТЗ-35)

Шаги FSM: `experience` → `phone` → `email` → `problem` → done  
(`questionnaire.STEPS`). ФИО/год рождения **не** спрашиваются.

| Payload | Шаг | Изменение | Эффект | Пробел |
|---|---|---|---|---|
| `q:exp:lt5\|5_10\|10_20\|gt20\|unknown` | experience | q_answers[experience] | next step | не период ИЛС |
| `q:skip:email` | email | email="" | next | — |
| `q:skip:middle_name` | legacy | ignore/compat | повтор шага | устар. |
| `q:fix_name` | legacy | ignore | повтор шага | устар. |
| текст phone/email/problem | текущий | normalize / validate | next или error | не callback |
| `menu:upload` | — | — | инструкция файлов | вне q FSM |
| `menu:docs` | — | remap `/docs` | docs flow | — |
| `menu:status` | — | status resolve | статус | SoT status |
| `menu:operator` | — | — | operator | — |

`файл::функция`:  
`questionnaire.py::apply_answer` / `_parse`  
`handler.py::_handle_questionnaire_or_menu`

## Закрытость этого дополнения

- [x] Перечислены payload builders `intake:` из `intake.py` + ветки handler
- [x] Перечислены `q:exp:*`, skip/fix legacy, menu:*
- [ ] Полный граф `_continue_after_*` helper’ов (не payload, но переходы)
- [ ] Тест на каждый subcode — нет; есть покрытые сценарии анкеты отдельно

Карта префиксов + subcodes достаточна для приоритизации дефектов.
Не считать «все callback защищены».
