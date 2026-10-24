# 2026-10-24 — SFRFR-83: quiet+kit честный статус

**PR:** https://github.com/kraskimira89-spec/sfrpfr/pull/258 (**без** auto-merge)  
**Эпик:** SFRFR-82 · **Задача:** SFRFR-83  
**Зависимость от #257:** нет (fiscal unit only).

## Критерий → изменение → тест → результат → блокер

| Критерий | Изменение | Тест | Результат | Блокер |
|---|---|---|---|---|
| Не врать «проверка идёт», когда анализ не запущен (quiet+полный комплект) | `client_case_status.reply_text`: при `receiving`+kit без `queued`/`running` → «ещё не запущена» | `test_quiet_kit_working_question_not_claiming_check_running` | pass | живой MAX smoke |
| Если check реально running в quiet — можно сказать «идёт» | та же ветка | `test_quiet_kit_working_question_when_check_running_may_say_in_progress` | pass | — |
| `kit_ready_no_analysis` без регрессии | без смены текстов kit_ready | существующие kit_ready tests | pass | — |
| Смежная регрессия brief/diag | — | `test_brief_analysis_offer` + `test_max_diag_choice` | 60 passed вместе со status | — |

## Исходное поведение

`working_question` при quiet и полном комплекте: «Краткая проверка ещё идёт или уже была» — даже без `document_check`.

## Границы

Цены / касса / E-F / OCR / amo не трогали.
