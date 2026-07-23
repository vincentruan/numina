"""L1/L2 single-source amortization — 6 cases (Plan B T4, spec §6.4)."""
from decimal import Decimal

from packages.domain.liability_calculator import AmortizationResult, calc_amortization


def test_equal_payment_amortization_normal():
    """等额本息正常: total_interest > 0, months finite, balance reaches ~0."""
    r = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                          monthly_payment=Decimal("3000"))
    assert r is not None
    assert r.total_interest > 0
    assert 30 <= r.months <= 50  # ~100k @12%, 3k/mo ≈ 38 months
    assert r.warning is None


def test_extra_payment_saves_interest_and_months():
    """提前还款省息: extra>0 → fewer months + less interest than baseline."""
    base = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                             monthly_payment=Decimal("3000"))
    extra = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                              monthly_payment=Decimal("3000"), extra_monthly=Decimal("500"))
    assert extra is not None and base is not None
    assert extra.total_interest < base.total_interest
    assert extra.months < base.months


def test_min_payment_covers_interest_credit_card():
    """最低还款覆盖利息: min_payment = max(remaining*5%, 100), covers interest."""
    # 10k @18% → monthly interest 150; min = max(500, 100) = 500 > 150 → covers.
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("18"),
                          monthly_payment=None, min_payment=Decimal("100"))
    assert r is not None
    assert r.months <= 1200
    assert r.warning is None
    assert r.total_interest > 0


def test_min_payment_does_not_cover_interest_warns():
    """最低还款不覆盖利息: warning set (still returns, capped at 1200 months)."""
    # 1,000,000 @60% → monthly interest 5000; min = max(50000, 100) = 50000.
    # principal = 50000 - 5000 = 45000 > 0 ... that covers. Force non-cover:
    # tiny min_payment floor so principal <= 0: min = max(50000, 100) is still 50000.
    # Use a rate high enough that interest >= min_payment: 1M @60% → interest 5000 < 50000.
    # To break coverage we need interest >= minimum: set min_payment floor BELOW interest
    # by making balance huge so 5% min still < interest? No — 5% of balance always > 1/12 rate.
    # The reliable non-cover path: min_payment floor (100) with balance small enough that
    # 5% of balance < 100 → min=100, but interest (balance*r/1200) > 100. E.g. balance=3000,
    # rate=60% → 5%=150>100 so min=150, interest=150 → principal=0. Use balance=1900:
    # 5%=95<100 → min=100, interest=1900*0.6/12=95 → principal=5>0 (covers).
    # balance=2100 @60%: 5%=105→min=105, interest=105 → principal=0 → warn. Use that.
    r = calc_amortization(remaining=Decimal("2100"), annual_rate=Decimal("60"),
                          monthly_payment=None, min_payment=Decimal("100"))
    assert r is not None
    # When 还本 <= 0 the util must warn (spec §6.1 "最低还款不足，建议增加月供").
    assert r.warning is not None
    assert r.months >= 1200 or r.warning  # capped or warned


def test_no_interest_rate_returns_none():
    """无利率: returns None — caller shows no interest region."""
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=None,
                          monthly_payment=Decimal("1000"))
    assert r is None
    r2 = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("0"),
                           monthly_payment=Decimal("1000"))
    assert r2 is None


def test_extra_ge_remaining_pays_off_immediately():
    """extra≥剩余本金: immediate payoff, ~0 interest, 1 month."""
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("12"),
                          monthly_payment=Decimal("1000"), extra_monthly=Decimal("15000"))
    assert r is not None
    assert r.total_interest < Decimal("200")  # ~1 month of interest only
    assert r.months <= 2


def test_result_shape():
    """AmortizationResult is a dataclass with the documented fields."""
    r = calc_amortization(remaining=Decimal("1000"), annual_rate=Decimal("12"),
                          monthly_payment=Decimal("500"))
    assert isinstance(r, AmortizationResult)
    assert hasattr(r, "total_interest")
    assert hasattr(r, "months")
    assert hasattr(r, "monthly_payment")
    assert hasattr(r, "warning")
    assert hasattr(r, "schedule")
