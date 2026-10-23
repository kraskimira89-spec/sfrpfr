# 2026-10-23 — снятие лишнего прихода FD 778

Владелец: «778 удаляй».

## Контекст

Платёж `326d821f-000f-5001-9000-1a272330e2d3` (первый SUPPORT 8000):
- 2× `type=payment` (FD **777** без settlements = invoice; FD **778** с settlements = ensure)
- 1× денежный refund `326d87d8-…` + 1× `type=refund` → net в ОФД было **+8000**

Удалить FD из ФН нельзя. Сделан **второй фискальный** `type=refund` на тот же `refund_id` (без повторного возврата денег).

## Действие

| Поле | Значение |
|------|----------|
| API | `POST /v3/receipts` `type=refund`, `refund_id=326d87d8-…93ee` |
| Receipt | `ra-326d9272-0000-0051-3e02-9495944fcec0` |
| Status | **succeeded** (`registered_at` 2026-10-23T12:35:00Z) |
| Amount | **8000.00** |
| settlements | cashless (как у ensure FD 778) |
| Описание позиции | «Коррекция дубля FD778 — возврат прихода 8000 (ensure)» |
| Деньги клиенту | **не** двигались повторно (`refunded_amount` уже был 8000.00) |

## Итог по `GET /receipts`

| type | count succeeded |
|------|-----------------|
| payment | **2** |
| refund | **2** |
| **net** | **0** |

FD в API `fiscal_document_number` = null — номер нового чека смотреть в Evotor / ОФД.
