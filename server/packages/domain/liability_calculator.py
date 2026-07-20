"""Single-source amortization model for L1 (strategy) + L2 (interest forecast).

spec §6.1: BACKEND-ONLY (no dual-language drift). The frontend L2 simulate modal
calls POST /liabilities/simulate; no amortization logic in TS.

Two modes:
- Equal-payment (monthly_payment given): 每月 利息 = 剩余 × 月利率, 还本 = 月供 - 利息.
- Minimum-payment (monthly_payment None, e.g. credit card): 最低 = max(剩余×5%, min_payment),
  还本 = max(最低 - 利息, 0). When 还本 <= 0 → warning "最低还款不足，建议增加月供".

extra_monthly increases the effective payment (月供 + extra) and the caller
compares baseline vs extra to report 省息/提前月数.

No interest_rate (None or 0) → returns None (caller shows no interest region).
Cap at 1200 months (100 years) to prevent infinite loops on pathological inputs.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

MAX_MONTHS = 1200  # 100-year cap — backstop against non-converging inputs.
TWO_PLACES = Decimal("0.01")
# Half-cent tolerance: a sub-cent balance is treated as paid off.
BALANCE_TOLERANCE = Decimal("0.005")


@dataclass
class AmortizationResult:
    total_interest: Decimal
    months: int
    monthly_payment: Decimal | None  # None when min-payment mode computed internally
    warning: str | None = None  # set when 最低还款不足 or hit MAX_MONTHS cap
    schedule: list[dict] | None = field(default=None)  # optional month-by-month (L2 baseline)


def _q(v: Decimal) -> Decimal:
    """Quantize to 2 decimals (cents)."""
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calc_amortization(
    remaining: Decimal,
    annual_rate: Decimal | None,
    monthly_payment: Decimal | None,
    extra_monthly: Decimal = Decimal("0"),
    min_payment: Decimal = Decimal("100"),
) -> AmortizationResult | None:
    """Iterate month-by-month to payoff. Returns None when no usable rate.

    Args:
      remaining: current principal balance.
      annual_rate: annual interest rate as a percent (e.g. 12 for 12%). None/0 → None.
      monthly_payment: fixed monthly payment (equal-payment mode). None → min-payment mode.
      extra_monthly: additional monthly principal payment (L2 "若每月多还 ¥X").
      min_payment: floor for the minimum payment in min-payment mode (default ¥100).
    """
    if annual_rate is None or annual_rate <= 0 or remaining <= 0:
        return None

    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    balance = Decimal(remaining)
    total_interest = Decimal("0")
    months = 0
    warning: str | None = None
    use_min_mode = monthly_payment is None
    extra = extra_monthly or Decimal("0")
    # Effective payment in equal-payment mode is fixed; in min-mode it's recomputed each iter.
    fixed_payment = (monthly_payment or Decimal("0")) + extra

    while balance > BALANCE_TOLERANCE:
        if months >= MAX_MONTHS:
            warning = "已达最大迭代月数（100 年），请增加月供或检查利率输入"
            break
        interest = _q(balance * monthly_rate)
        if use_min_mode:
            minimum = max(_q(balance * Decimal("0.05")), min_payment)
            effective_payment = minimum + extra
            principal = effective_payment - interest
            if principal <= 0:
                warning = "最低还款不足覆盖利息，建议增加月供"
                # Still accrue interest; principal stays 0 → loop hits MAX_MONTHS.
                principal = Decimal("0")
        else:
            principal = fixed_payment - interest
            if principal <= 0:
                # Fixed payment doesn't cover interest — can't converge.
                warning = "月供不足以覆盖利息，请增加月供"
                break
        # Don't overpay past the balance.
        principal = min(principal, balance)
        balance = _q(balance - principal)
        total_interest = _q(total_interest + interest)
        months += 1

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=months,
        monthly_payment=fixed_payment if not use_min_mode else None,
        warning=warning,
    )
