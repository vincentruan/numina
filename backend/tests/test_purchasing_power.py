from app.services.purchasing_power import calculate_purchasing_power


def test_lookback_2015_to_2025():
    """2015年的10万元，到2025年应该增值（通胀侵蚀购买力）。"""
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2015, to_year=2025
    )
    assert result["original_amount"] == 100000.0
    assert result["adjusted_amount"] > 100000.0
    assert result["cumulative_inflation"] > 0
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert "explanation" in result


def test_lookback_same_year():
    result = calculate_purchasing_power(amount=50000.0, from_year=2020, to_year=2020)
    assert result["adjusted_amount"] == 50000.0
    assert result["cumulative_inflation"] == 0.0


def test_custom_inflation_rate():
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2020, to_year=2025, custom_inflation_rate=0.05
    )
    expected = round(100000.0 * (1.05 ** 5), 2)
    assert abs(result["adjusted_amount"] - expected) < 0.01


def test_auto_swap_years():
    """from_year > to_year 时自动交换。"""
    result = calculate_purchasing_power(amount=10000.0, from_year=2025, to_year=2015)
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert result["adjusted_amount"] > 10000.0
