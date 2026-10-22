# 2026-10-22 — soft-ask «Да» → no_discrepancy после #188

**Ветка:** `fix/soft-ask-preserve-gaps`  
**Контекст:** browser smoke после #188: не receiving и не оффер 3000, а отказ
«По краткому разбору явных расхождений не видно…».

## Почему soft-ask был, а gate = no_discrepancy

1. Soft-ask уходит только при `has_justified_discrepancy` (`run_brief_after_kit`).
2. После restart `problem` в `q_answers` стирался; `_brief_*` могли быть неполны.
3. `ensure_brief_flags_for_offer` пересчитывал brief без problem / без чата →
   `has_justified_discrepancy=False` → persist писал `_brief_discrepancy=0`.
4. `evaluate_diag_offer` → `DENY_NO_DISCREPANCY` → текст про «расхождений не видно».

Heal **перетирал** gaps: не «сохранял `_brief_has_gaps`», а заново писал discrepancy
из пустого пересчёта.

## Что видит heal для user 79841100

- `_problem_text`: анкета `problem` / `problem_type` / `goal` + реплики клиента из
  `case_messages` (`author_kind` client/user/representative; пустой kind тоже).
- Если restart стёр `problem` и история пуста/без «север» — themes пустые → no gaps.
- Северный стаж из чата: паттерн `север|ркс|мкс|…` в `_PROBLEM_THEMES`.

## Фикс

| Место | Что |
|---|---|
| `_brief_soft_ask_sent` | ставится при показе soft-ask; переживает restart |
| `preserve_gaps_after_soft_ask_yes` | payload `diag:detail_yes` = soft-ask уже был → gaps для gate |
| `ensure_brief_flags_for_offer` | не даёт soft-ask/gaps откатиться в пустой no_discrepancy |
| `intake.restart` | сохраняет `problem`, `goal`, `problem_type` |
| soft-ask | по-прежнему только при `has_justified_discrepancy` |

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_brief_analysis_offer.py `
  tests/unit/test_client_case_status_loop.py `
  tests/unit/test_max_diag_choice.py `
  --basetemp=tmp/pytest-soft-ask-preserve -q
```

Живой MAX (user с soft-ask в ленте): «Да, подробный разбор» → оффер 3 000 ₽,
не «расхождений не видно» и не receiving.
