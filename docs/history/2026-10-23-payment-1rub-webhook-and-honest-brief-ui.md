# 2026-10-23 — 1₽ webhook + честный UI резюме

**Вердикт:** код и тестовая цепочка на 1₽ готовы; боевая приёмка тарифов не проведена.

## Платёж 1₽ (явное «да платим 1 руб» владельца)

| Поле | Значение (masked) |
|------|-------------------|
| Shop VPS | `1421177` |
| Флаг | `PAYMENT_TEST_AMOUNT_ENABLED=1` → после оплаты **`=0`** (environ API) |
| Дело | ПС-102137 / CASE-2026-102137 (`6721f530-…8ef9`, `is_test`) — не 600855 |
| Order | `81eb7116-…cb0a3`, amount_rub витрины 3000, charge **1.00** |
| Payment | `326d17bf-…8677`, status **succeeded**, paid |
| Webhook | Apache `POST …/yookassa/webhook` **200** (09:52 +0300); order → **paid**, b2c **diagnostic_paid** без reconcile |
| Повтор | `order_already_paid`, второго счёта нет |
| Чек | `receipt_registration=canceled` — **смена Evotor**, напомнить кассе |

## UI честного резюме

- `honest_brief_ui_payload`: docs / client / needs_check; ≤3; основание; офер 3000 только при docs\|needs_check; stale по fingerprint.
- Staff «Проверить документы» → `honest_brief` + `diag_offer` в результате; блок в `case-funnel-main`.

## Не сделано

Боевая приёмка 3000/5000/8000 ₽ — ждём отдельное «да, платим» владельца.
