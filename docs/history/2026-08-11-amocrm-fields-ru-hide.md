# 2026-08-11 — amoCRM: русские названия полей, скрытие черновиков

## Что сделано

- В `LEAD_FIELD_SPECS` все названия на русском.
- Черновики оплат / success fee (`DIAGNOSTIC_PAID_AT` … `SUCCESS_FEE_*`) — `is_api_only=true` (не видны оператору).
- `amocrm-ensure-fields` теперь ещё и `PATCH` имён / `is_api_only`.
- Применено в аккаунте proverkastaza; docs ops/AMO обновлены.

## Зачем

Операторская карточка на русском; неиспользуемые до юр. модели поля не засоряют UI.
