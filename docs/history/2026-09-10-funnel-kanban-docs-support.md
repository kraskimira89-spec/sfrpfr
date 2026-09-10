# История: kanban воронки + офферы 5/8 тыс.

## 2026-09-10

Реализовано ТЗ-33 и стратегия LLM→5/8:

- `src/sfrfr/services/funnel_board.py` — `compute_funnel_column`, тарифы DIAG/DOCS/SUPPORT
- Admin board: колонки 3/5/8, бейдж тарифа, API `/admin/funnel-board*`
- `max_bot_invoice`: DOCS после выдачи диагностики; SUPPORT после DOCS paid + проект обращения
- Pay link после оферты для любого открытого шага (не только DIAG)
- LLM prompt: канон цен и ворот; кнопки `offer:docs` / `offer:support`
- Починен битый `handler.py` (отступы из 2e32bf2c) — база `c554fcc2` + offer-callbacks

Проверка: `pytest tests/unit/test_funnel_board.py tests/unit/test_sales_board.py tests/unit/test_finance_automation.py tests/unit/test_max_bot_owned.py`
