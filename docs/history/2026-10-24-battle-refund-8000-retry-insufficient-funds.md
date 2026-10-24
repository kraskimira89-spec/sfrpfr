# 2026-10-24 — возврат повторного SUPPORT 8000: insufficient funds

**Вердикт: ❌ деньги не возвращены** (API `403`)

Владелец: «верни 8000». Цель — **повторный** SUPPORT (PASS 2026-10-23), не первый FAIL (тот уже был возвращён ранее).

## Попытка

| Поле | Значение |
|------|----------|
| Shop | **1421177** |
| Платёж | повторный SUPPORT 8000 (см. `2026-10-23-battle-support-8000-retry.md`) |
| Amount | **8000.00** |
| До | status `succeeded`, `refunded_amount=0.00`, `receipt_registration=succeeded` |
| HTTP | **403** |
| Error | `Insufficient funds to make a refund. Contact support to find out the reason.` |
| Чеки после | 1× `type=payment` succeeded; **0×** `type=refund` |
| После сверки | `refunded_amount` по-прежнему **0.00** |

## Не трогали

- Первый SUPPORT (уже полный refund ранее)
- Smoke 1₽
- Новый платёж / новый чек прихода
- Флаг тестовой суммы (остался выключен)

## Что нужно владельцу

1. Пополнить баланс ЮKassa shop **1421177** (или уточнить у поддержки ЮKassa причину нехватки средств на refund — часто после выплаты на р/с).
2. Повторить команду «верни 8000» после пополнения.

Полные payment/refund id и контакты клиента в этот файл **не** кладём (см. паспорт SFRFR-100).
