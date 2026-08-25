# 2026-08-25 — MAX-first Sprint 2: consent + view PDF

## Сделано

- Публичные страницы `/api/portal/secure/{token}` (HTML + JSON).
- Consent без регистрации; view_pdf → signed storage URL.
- Admin issue: `POST .../admin/cases/{id}/secure-links`.
- Payment notify: кнопка согласия при `MAX_SECURE_LINK_BUTTONS_ENABLED`.
- Тесты: `tests/unit/test_secure_actions_sprint2.py`.

## Флаги (staging)

```text
SECURE_ACTION_LINKS_ENABLED=1
SECURE_RESULT_VIEW_ENABLED=1   # только для PDF
MAX_SECURE_LINK_BUTTONS_ENABLED=1  # кнопка после оплаты
```

Default на prod — всё `0`. `/diag-share` не трогали.

## Не делали

Upload UI, cutover MAX FSM, удаление кабинета.
