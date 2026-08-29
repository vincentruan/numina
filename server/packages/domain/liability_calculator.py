"""Single-source amortization model for L1 (strategy) + L2 (interest forecast).

spec §6.1: BACKEND-ONLY (no dual-language drift). The frontend L2 simulate modal
calls POST /liabilities/simulate; no amortization logic in TS.

Five repayment methods:
- equal_payment (等额本息): fixed monthly payment. monthly_payment required.
- equal_principal (等额本金): fixed monthly principal, decreasing payment. total_periods required.
- interest_only (先息后本): interest each period, principal at end. total_periods required.
- bullet (一次性还本): single payment at maturity. total_periods required.
- minimum_payment (最低还款): credit card mode. monthly_payment None.

extra_monthly increases the effective payment (月供 + extra) and the caller
compares baseline vs extra to report 省息/提前月数. Only applies to equal_payment.

No interest_rate (None or 0) → returns None (caller shows no interest region).
Cap at 1200 months (100 years) to prevent infinite loops on pathological inputs.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

MAX_MONTHS = 1200  # 100-year cap — backstop against non-converging inputs.
TWO_PLACES = Decimal("0.01")
# Half-cent tolerance: a sub-cent balance is treated as paid off.
BALANCE_TOLERANCE = Decimal("0.005")

# Valid repayment method values.
VALID_METHODS = frozenset({
    "equal_payment",
    "equal_principal",
    "interest_only",
    "bullet",
    "minimum_payment",
})


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
    repayment_method: str = "equal_payment",
    total_periods: int | None = None,
) -> AmortizationResult | None:
    """Iterate month-by-month to payoff. Returns None when no usable rate.

    Args:
      remaining: current principal balance.
      annual_rate: annual interest rate as a percent (e.g. 12 for 12%). None/0 → None.
      monthly_payment: fixed monthly payment (equal-payment mode). None → min-payment mode.
      extra_monthly: additional monthly principal payment (L2 "若每月多还 ¥X").
      min_payment: floor for the minimum payment in min-payment mode (default ¥100).
      repayment_method: one of equal_payment/equal_principal/interest_only/bullet/minimum_payment.
      total_periods: total number of periods (required for equal_principal/interest_only/bullet).
    """
    if annual_rate is None or annual_rate <= 0 or remaining <= 0:
        return None

    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    balance = Decimal(remaining)

    # Route to method-specific calculator
    if repayment_method == "equal_principal":
        return _calc_equal_principal(balance, monthly_rate, total_periods)
    elif repayment_method == "interest_only":
        return _calc_interest_only(balance, monthly_rate, total_periods)
    elif repayment_method == "bullet":
        return _calc_bullet(balance, monthly_rate, total_periods)
    elif repayment_method == "minimum_payment" or monthly_payment is None:
        return _calc_minimum_payment(balance, monthly_rate, extra_monthly, min_payment)
    else:
        return _calc_equal_payment(balance, monthly_rate, monthly_payment, extra_monthly)


def _calc_equal_payment(
    balance: Decimal,
    monthly_rate: Decimal,
    monthly_payment: Decimal,
    extra_monthly: Decimal,
) -> AmortizationResult | None:
    """Equal-payment (等额本息): fixed monthly payment, interest decreases over time."""
    total_interest = Decimal("0")
    months = 0
    warning: str | None = None
    extra = extra_monthly or Decimal("0")
    fixed_payment = monthly_payment + extra

    while balance > BALANCE_TOLERANCE:
        if months >= MAX_MONTHS:
            warning = "已达最大迭代月数（100 年），请增加月供或检查利率输入"
            break
        interest = _q(balance * monthly_rate)
        principal = fixed_payment - interest
        if principal <= 0:
            warning = "月供不足以覆盖利息，请增加月供"
            break
        principal = min(principal, balance)
        balance = _q(balance - principal)
        total_interest = _q(total_interest + interest)
        months += 1

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=months,
        monthly_payment=fixed_payment,
        warning=warning,
    )


def _calc_minimum_payment(
    balance: Decimal,
    monthly_rate: Decimal,
    extra_monthly: Decimal,
    min_payment: Decimal,
) -> AmortizationResult | None:
    """Minimum-payment (最低还款): credit card mode."""
    total_interest = Decimal("0")
    months = 0
    warning: str | None = None
    extra = extra_monthly or Decimal("0")

    while balance > BALANCE_TOLERANCE:
        if months >= MAX_MONTHS:
            warning = "已达最大迭代月数（100 年），请增加月供或检查利率输入"
            break
        interest = _q(balance * monthly_rate)
        minimum = max(_q(balance * Decimal("0.05")), min_payment)
        effective_payment = minimum + extra
        principal = effective_payment - interest
        if principal <= 0:
            warning = "最低还款不足覆盖利息，建议增加月供"
            principal = Decimal("0")
        principal = min(principal, balance)
        balance = _q(balance - principal)
        total_interest = _q(total_interest + interest)
        months += 1

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=months,
        monthly_payment=None,
        warning=warning,
    )


def _calc_equal_principal(
    balance: Decimal,
    monthly_rate: Decimal,
    total_periods: int | None,
) -> AmortizationResult | None:
    """Equal-principal (等额本金): fixed monthly principal, decreasing interest."""
    if not total_periods or total_periods <= 0:
        return None

    monthly_principal = _q(balance / total_periods)
    total_interest = Decimal("0")
    schedule: list[dict] = []

    for month in range(1, total_periods + 1):
        interest = _q(balance * monthly_rate)
        payment = monthly_principal + interest
        payment = min(payment, balance + interest)  # last period: don't overpay
        principal = payment - interest
        principal = min(principal, balance)
        balance = _q(balance - principal)
        total_interest = _q(total_interest + interest)
        schedule.append({
            "month": month,
            "payment": _q(payment),
            "principal": _q(principal),
            "interest": _q(interest),
            "balance": _q(balance),
        })
        if balance <= BALANCE_TOLERANCE:
            break

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=len(schedule),
        monthly_payment=schedule[0]["payment"] if schedule else None,
        schedule=schedule,
    )


def _calc_interest_only(
    balance: Decimal,
    monthly_rate: Decimal,
    total_periods: int | None,
) -> AmortizationResult | None:
    """Interest-only (先息后本): interest each period, full principal at end."""
    if not total_periods or total_periods <= 0:
        return None

    monthly_interest = _q(balance * monthly_rate)
    total_interest = Decimal("0")
    schedule: list[dict] = []

    for month in range(1, total_periods + 1):
        if month < total_periods:
            # Interest-only period
            payment = monthly_interest
            principal = Decimal("0")
            total_interest = _q(total_interest + monthly_interest)
        else:
            # Final period: interest + full principal
            payment = monthly_interest + balance
            principal = balance
            total_interest = _q(total_interest + monthly_interest)
            balance = Decimal("0")

        schedule.append({
            "month": month,
            "payment": _q(payment),
            "principal": _q(principal),
            "interest": _q(monthly_interest),
            "balance": _q(balance),
        })

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=total_periods,
        monthly_payment=monthly_interest,
        schedule=schedule,
    )


def _calc_bullet(
    balance: Decimal,
    monthly_rate: Decimal,
    total_periods: int | None,
) -> AmortizationResult | None:
    """Bullet (一次性还本): single payment at maturity covering principal + all interest."""
    if not total_periods or total_periods <= 0:
        return None

    total_interest = _q(balance * monthly_rate * total_periods)
    payment = balance + total_interest

    schedule = [{
        "month": total_periods,
        "payment": _q(payment),
        "principal": _q(balance),
        "interest": _q(total_interest),
        "balance": Decimal("0"),
    }]

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=total_periods,
        monthly_payment=None,
        schedule=schedule,
    )
