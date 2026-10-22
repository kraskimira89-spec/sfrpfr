# 2026-10-22 — MAX funnel R1: честное резюме и статусы

**Трекер:** [SFRFR-82](https://tracker.yandex.ru/SFRFR-82) (+ SFRFR-83…87)
**Ветка:** `fix/max-funnel-honest-brief-r1`

## Зачем

Владелец: цепочка «что получили → что выяснили → за что платим → что после оплаты».
Три дефекта до усиления продаж:

1. Анкета смешивалась с найденной проблемой.
2. Клик soft-ask восстанавливал флаги «анализ выполнен».
3. `kit_ready_no_analysis` говорил, что проверка уже идёт.

## R1 сделано

| Зона | Изменение |
|---|---|
| `brief_analysis` | Основания пунктов: docs / client / needs_check; ≤3 bullets + next step; soft-ask только docs\|needs_check; goal не подмешивается |
| `preserve_gaps*` | Revive оффера только если soft-ask уже был; клик ≠ proof анализа (`_brief_offer_revive`) |
| `diag_choice` | `diag:detail_yes` при уже оплаченной DIAG → next step, не повторная продажа |
| `client_case_status` | Честный текст: комплект есть, краткий анализ ещё не запущен |

## Границы (не трогали)

Цены 3000/5000/8000, касса, PAYMENT_TEST_AMOUNT, AmoCRM, OCR, E/F, содержание пакета 5000.

## Дальше

- R2: post-pay confirmation recover (SFRFR-86)
- Этапы 5000 (DOCS после DIAG) и 8000 — по канону тарифов, без незаметной смены пакета 5k
- Живой smoke MAX + staff cabinet после deploy

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_brief_analysis_offer.py `
  tests/unit/test_client_case_status_loop.py `
  tests/unit/test_max_diag_choice.py `
  --basetemp=tmp/pytest-r1b -q
# → 50 passed
```
