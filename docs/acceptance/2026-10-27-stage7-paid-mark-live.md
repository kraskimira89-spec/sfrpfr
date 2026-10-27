# Живая проверка paid → done (без боевого платежа)

**Дата:** 2026-10-27
**Дело:** `1579e69f-f74f-4c38-9fb1-c65493afe3c4`
**Контур:** admin `POST …/orders/{id}/mark-paid` (не ЮKassa, не клиент)

## Результат

| Шаг | Итог |
|---|---|
| Create ACCOMP 5000 pending | 201 `274b2db0-…` |
| mark-paid `method=other` | 200 |
| `orders.status` | `paid` |
| `b2c_status` | `service_paid` |
| Derive `appeals_payment` | done при paid ACCOMP 5000 (unit + facts) |

Боевую оплату и ссылку клиенту не отправляли. Счёт-probe остаётся paid в истории дела (тестовое).
