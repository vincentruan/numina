"""L2 /liabilities/simulate request/response (Plan B T4).

Pure-compute endpoint (no db write). Money fields are Decimal in the util,
serialized as str (2 decimals) per the numeric-as-string convention.
"""
from decimal import Decimal

from pydantic import BaseModel, field_validator


class SimulateRequest(BaseModel):
    remaining: Decimal
    annual_rate: Decimal
    monthly_payment: Decimal | None = None
    extra_monthly: Decimal = Decimal("0")
    repayment_method: str = "equal_payment"
    total_periods: int | None = None


class SimulateResponse(BaseModel):
    total_interest: str  # Decimal → str (2 decimals)
    months: int
    monthly_payment: str | None
    warning: str | None
    # Only present when extra_monthly > 0 (the L2 "省 ¥Y, 提前 N 月" comparison):
    baseline_total_interest: str | None = None
    baseline_months: int | None = None
    savings_vs_baseline: str | None = None
    months_saved: int | None = None
    # Optional month-by-month schedule (for equal_principal/interest_only/bullet):
    schedule: list[dict] | None = None

    @field_validator(
        "total_interest",
        "monthly_payment",
        "baseline_total_interest",
        "savings_vs_baseline",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        if v is None:
            return None
        return str(Decimal(v).quantize(Decimal("0.01")))
