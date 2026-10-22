"""Тестовая сумма ЮKassa: 1 ₽ при test-ключе / флаге, тариф на live."""

from __future__ import annotations

from typing import Any

from sfrfr.services.payment_amount import (
    is_yookassa_test_shop,
    yookassa_charge_amount_rub,
)


def test_live_shop_keeps_tariff_amount() -> None:
    assert (
        yookassa_charge_amount_rub(
            3000.0,
            secret_key="live_xxxxxxxx",
            test_amount_rub=1.0,
            force_enabled=False,
        )
        == 3000.0
    )


def test_test_shop_key_uses_one_ruble() -> None:
    assert (
        yookassa_charge_amount_rub(
            3000.0,
            secret_key="test_xxxxxxxx",
            test_amount_rub=1.0,
            force_enabled=False,
        )
        == 1.0
    )


def test_force_flag_overrides_even_on_live_key() -> None:
    assert (
        yookassa_charge_amount_rub(
            5000.0,
            secret_key="live_xxxxxxxx",
            test_amount_rub=1.0,
            force_enabled=True,
        )
        == 1.0
    )


def test_zero_test_amount_disables_override() -> None:
    assert (
        yookassa_charge_amount_rub(
            8000.0,
            secret_key="test_xxxxxxxx",
            test_amount_rub=0.0,
            force_enabled=True,
        )
        == 8000.0
    )


def test_is_yookassa_test_shop_detects_prefix() -> None:
    assert is_yookassa_test_shop("test_abc") is True
    assert is_yookassa_test_shop("live_abc") is False
    assert is_yookassa_test_shop("") is False
    assert is_yookassa_test_shop(None) is False


def test_settings_wire_default_one_rub(monkeypatch: Any) -> None:
    from sfrfr.core.config import Settings, get_settings
    from sfrfr.services import payment_amount as mod

    get_settings.cache_clear()
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test_unit_key")
    monkeypatch.setenv("PAYMENT_TEST_AMOUNT_RUB", "1")
    monkeypatch.delenv("PAYMENT_TEST_AMOUNT_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        settings = Settings()
        monkeypatch.setattr(mod, "get_settings", lambda: settings)
        assert yookassa_charge_amount_rub(3000.0) == 1.0
    finally:
        get_settings.cache_clear()
