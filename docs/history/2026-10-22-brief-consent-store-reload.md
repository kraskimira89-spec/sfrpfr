# 2026-10-22 — soft-ask «Да» → gate no_analysis + brief без problem

**Ветка:** `fix/brief-consent-store-reload`  
**Контекст:** после browser smoke #185/#186 оффер 3000 появился; процесс ломался.

## Причины

1. **Stale intake store.** Brief (CLI / другой воркер) писал `_brief_*` в `max_intake.json`, uvicorn держал in-memory без флагов; `mark_detail_consent` сохранял stale `q_answers` и затирал brief → gate `no_analysis`.
2. **Пустой `q_answers.problem`.** Brief смотрел только анкетный `problem`; формулировка из чата / `goal` / `problem_type` не учитывалась → «нет расхождений», без soft-ask.
3. **Статус после brief.** Quiet/`receiving` перекрывал `result_ready` → «Спасибо» / working_question отвечали «обрабатываем».

## Фикс

| Место | Что |
|---|---|
| `MaxIntakeStore.reload` + `save` | reload с диска; merge сохраняет `_brief_*` при stale overlay |
| `mark_detail_consent` / persist / summary | `_reload_intake_rec` перед записью |
| `gate_flags_from_intake(..., reload=True)` | diag soft-ask / pay |
| `_problem_text` | анкета + goal/type + `client_texts` из ленты |
| `client_case_status.resolve` | `result_ready` выше quiet |
| settle | тест: complete → `schedule_brief_after_kit` |

Не открывали F (5k/8k). SFRFR-69 не закрывали. Оплату не проводили.

## Как проверить «Да» после soft-ask (без CLI)

1. Анкета с проблемой *или* реплика «не учли северный стаж» + ИЛС + трудовая в MAX.
2. Дождаться settle → краткий разбор + soft-ask.
3. «Да, подробный разбор» → оффер 3 000 ₽ (не `no_analysis`).
4. «Спасибо» / «Вы ещё работаете?» → текст итога/статуса, не шаблон «обрабатываем».

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_brief_analysis_offer.py `
  tests/unit/test_client_case_status_loop.py `
  tests/unit/test_max_diag_choice.py `
  tests/unit/test_tz35_owner_pass.py `
  --basetemp=tmp/pytest-brief-fix -q
```
