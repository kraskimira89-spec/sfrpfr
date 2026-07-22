"""Расчёт success fee для B2C (ЕДВ + ежемесячная прибавка)."""

from __future__ import annotations

from typing import TypedDict

SF_LUMP_RATE = 0.10
SF_MONTH_RATE = 0.50
SF_MONTHS = 3
SUCCESS_FEE_DELAY_DAYS_MIN = 60
SUCCESS_FEE_DELAY_DAYS_MAX = 90


class SuccessFeeBreakdown(TypedDict):
    sf_lump: float
    sf_month: float
    sf_total: float
    lump_sum_rub: float
    monthly_increase_rub: float


def calc_success_fee(
    *,
    lump_sum_rub: float = 0.0,
    monthly_increase_rub: float = 0.0,
) -> SuccessFeeBreakdown:
    """Вернуть разбивку success fee.

    SF_LUMP  = 10% от ЕДВ
    SF_MONTH = 50% от суммы прибавок за первые 3 месяца
    """
    lump = max(float(lump_sum_rub), 0.0)
    monthly = max(float(monthly_increase_rub), 0.0)
    sf_lump = round(lump * SF_LUMP_RATE, 2) if lump > 0 else 0.0
    sf_month = round(monthly * SF_MONTHS * SF_MONTH_RATE, 2) if monthly > 0 else 0.0
    return {
        "sf_lump": sf_lump,
        "sf_month": sf_month,
        "sf_total": round(sf_lump + sf_month, 2),
        "lump_sum_rub": lump,
        "monthly_increase_rub": monthly,
    }
