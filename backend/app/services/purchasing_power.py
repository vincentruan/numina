"""购买力计算引擎。"""

from app.constants.cpi import CHINA_CPI_ANNUAL, DEFAULT_INFLATION_RATE


def calculate_purchasing_power(
    amount: float,
    from_year: int,
    to_year: int,
    custom_inflation_rate: float | None = None,
) -> dict:
    if from_year > to_year:
        from_year, to_year = to_year, from_year

    years = to_year - from_year
    if years == 0:
        return {
            "original_amount": amount,
            "adjusted_amount": amount,
            "from_year": from_year,
            "to_year": to_year,
            "cumulative_inflation": 0.0,
            "annual_avg_inflation": 0.0,
            "explanation": f"{from_year}年的{amount:.0f}元，仍然是{amount:.0f}元",
        }

    # 逐年复合计算
    factor = 1.0
    for y in range(from_year, to_year):
        if custom_inflation_rate is not None:
            rate = custom_inflation_rate
        else:
            rate = CHINA_CPI_ANNUAL.get(y, DEFAULT_INFLATION_RATE * 100) / 100.0
        factor *= 1 + rate

    adjusted = round(amount * factor, 2)
    cumulative = round((factor - 1) * 100, 2)
    annual_avg = round(((factor ** (1.0 / years)) - 1) * 100, 2) if years > 0 else 0.0

    explanation = f"{from_year}年的{amount:.0f}元，相当于{to_year}年的{adjusted:.0f}元"

    return {
        "original_amount": amount,
        "adjusted_amount": adjusted,
        "from_year": from_year,
        "to_year": to_year,
        "cumulative_inflation": cumulative,
        "annual_avg_inflation": annual_avg,
        "explanation": explanation,
    }
