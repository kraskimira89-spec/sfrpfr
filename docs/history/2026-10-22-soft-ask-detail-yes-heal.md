# 2026-10-22 — soft-ask «Да» → gate + receiving после #187

**Ветка:** `fix/soft-ask-detail-yes-offer`  
**Контекст:** browser smoke после deploy #187 всё ещё FAIL.

## Прод (read-only)

| Поле | Значение |
|---|---|
| web.max.ru | `309063281` = `max_chat_id` |
| `max_user_id` | `79841100` |
| case | `c3074452-…` |
| `q_answers` на момент smoke | только `_detail_consent=1`, **без** `_brief_*` |
| commit на VPS | `0229da94` (#187) |

## Реальная ветка

1. Кнопка soft-ask: payload **`diag:detail_yes`** (`brief_analysis.DETAIL_YES`).
2. `diag_choice.handle` → `mark_detail_consent(True)` → `evaluate_diag_offer`.
3. Gate **`no_analysis`** (нет `_brief_*` после restart / wipe).
4. `_gated_reply` клеил `reply_text(receiving)` → «Подробную диагностику…» + «Документы получили. Сейчас обрабатываем…».

Оффер в 12:52 был раньше (CLI); новый soft-ask в ленте + intake без brief → повторный «Да» не в offer.

«Вы ещё работаете?» → `working_question` при `receiving` (quiet/pending) без brief → тот же шаблон.

## Фикс

| Место | Что |
|---|---|
| `ensure_brief_flags_for_offer` | на `diag:detail_yes` пересчитать brief из дела до consent |
| `_gated_reply` | не клеить receiving; честная причина gate |
| `MaxIntakeStore.restart` | сохранить `_brief_*` / `_detail_*` / `_diag_step` + case_id |
| `reply_text(working_question)` | полный комплект + receiving → не «обрабатываем» |

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_brief_analysis_offer.py `
  tests/unit/test_client_case_status_loop.py `
  tests/unit/test_max_diag_choice.py `
  --basetemp=tmp/pytest-soft-ask -q
```

Живой MAX: soft-ask «Да» → оффер 3000; «Вы ещё работаете?» → не «обрабатываем».
