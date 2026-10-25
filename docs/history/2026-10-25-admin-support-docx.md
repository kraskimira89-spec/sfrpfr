# 2026-10-25 — SUPPORT package_code + DOCX черновика

## SUPPORT

- `package_code=SUPPORT` (8 000 ₽) отдельно от ACCOMP 5 000.
- Старые заказы ACCOMP×8000 читаются как legacy, без переклассификации.
- UI: опция SUPPORT, кнопка счёта на ступени эскалации.

## DOCX

- `GET /api/portal/admin/cases/{id}/appeal-docx` — скачивание из pipeline draft.
- Без автоотправки клиенту; только сотрудник.

## Не в этом PR

Глобальный sync 13 ступеней в Трекер; production-миграции; боевые платежи.
