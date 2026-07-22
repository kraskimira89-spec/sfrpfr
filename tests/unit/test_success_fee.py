from sfrfr.core.success_fee import calc_success_fee


def test_success_fee_lump_and_month() -> None:
    result = calc_success_fee(lump_sum_rub=100_000, monthly_increase_rub=5_000)
    assert result["sf_lump"] == 10_000.0
    assert result["sf_month"] == 7_500.0
    assert result["sf_total"] == 17_500.0


def test_success_fee_zero_without_increase() -> None:
    result = calc_success_fee(lump_sum_rub=0, monthly_increase_rub=0)
    assert result["sf_total"] == 0.0
