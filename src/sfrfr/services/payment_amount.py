"""Сумма для create payment / invoice ЮKassa.

Публичные тарифы (3000/5000/8000) и orders.amount_rub не меняем.
В test-магазине ЮKassa (секрет `test_…`) или при явном флаге
в провайдер уходит PAYMENT_TEST_AMOUNT_RUB (канон: 1.00).
"""

from __future__ import annotations

from sfrfr.core.config import get_settings


def is_yookassa_test_shop(secret_key: str | None) -> bool:
    """Секрет тестового магазина ЮKassa начинается с `test_`."""
    return str(secret_key or "").strip().lower().startswith("test_")


def yookassa_charge_amount_rub(
    order_amount_rub: float,
    *,
    secret_key: str | None = None,
    test_amount_rub: float | None = None,
    force_enabled: bool | None = None,
) -> float:
    """Сумма в API ЮKassa: test → 1 ₽ (или PAYMENT_TEST_AMOUNT_RUB), иначе тариф заказа."""
    amount = float(order_amount_rub or 0)
    settings = get_settings()
    key = secret_key if secret_key is not None else settings.yookassa_secret_key
    test_amt = (
        float(test_amount_rub)
        if test_amount_rub is not None
        else float(settings.payment_test_amount_rub)
    )
    forced = (
        bool(force_enabled)
        if force_enabled is not None
        else bool(settings.payment_test_amount_enabled)
    )
    if test_amt <= 0:
        return amount
    if forced or is_yookassa_test_shop(key):
        return test_amt
    return amount
