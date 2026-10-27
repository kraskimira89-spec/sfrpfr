# Регрессия этапа 5 перед ступенями 7–8

**Дата:** 2026-10-27  
**Цель:** убедиться, что этап 5 (согласование разбора) не сломан после этапа 6, до работ 7–8.

## Проверки

| Проверка | Результат |
|---|---|
| `toFunnelFacts: этап 5 закрыт только после full_analysis_approved` | PASS |
| approve v1 не закрывает при version:2 | PASS |
| этап 5 ≠ `appeals_consent_*` | PASS (этап 6 отдельно) |
| pytest `-k "full_analysis or stage5 or appeals"` | 22 passed |
| `case-funnel.test.ts` | 34 passed |

Этап 5 **не переоткрываем**. Дальше — ступени 7–8.
