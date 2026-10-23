# 2026-10-23 — перевыставление счёта DIAG на 3 ₽ (shop 1421177)

## Итог

| Поле | Значение |
|------|----------|
| Старый order | `f4464298-…b5b6` → **cancelled** (БД) |
| Старый invoice YK | `in-326d1ace-…1046` → **canceled** (ЛК merchant, party=merchant) |
| Новая ссылка | `https://yookassa.ru/my/i/atsMLhRF5SV-/a` |
| Charge / витрина | **3,00 ₽** |
| Новый order | `b28cc23c-…b873`, amount_rub 3000 (тариф), invoice pending |
| Новый invoice | `in-326d1fee-…6ff1` |
| Дело | ПС-275527 / `4ef915ef-…3447` (`is_test`) |
| Shop | **1421177** |
| `PAYMENT_TEST_AMOUNT_ENABLED` | окно `1` → сразу **`0`** (RUB=3 остаётся выкл.) |

Оплату агент не проводил — ждёт владельца.
