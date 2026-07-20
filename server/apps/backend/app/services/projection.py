"""财务推演计算引擎。"""

from datetime import date


def calculate_projection(
    assets: list[dict],
    liabilities: list[dict],
    history_points: list[dict],
    projection_years: int = 5,
    inflation_rate: float = 0.03,
    current_year: int | None = None,
    custom_overrides: dict[int, float] | None = None,
) -> dict:
    if current_year is None:
        current_year = date.today().year

    # Build per-asset projection parameters
    asset_projections = []
    for a in assets:
        asset_id = a.get("id")
        if custom_overrides and asset_id in custom_overrides:
            custom_rate = custom_overrides[asset_id]
            if a["asset_type"] == "financial":
                dep, ret = 0.0, custom_rate
            else:
                dep, ret = custom_rate, 0.0
        else:
            dep = a.get("annual_depreciation", 0.0)
            ret = a.get("annual_return", 0.0)
        asset_projections.append({
            "current_value": a.get("current_value", 0) or 0,
            "asset_type": a["asset_type"],
            "depreciation": dep,
            "annual_return": ret,
        })

    # Build liability projections
    liability_projections = []
    for li in liabilities:
        # remaining_amount/monthly_payment may be Decimal (model) or str (API);
        # coerce to float so the arithmetic below stays in one numeric type.
        liability_projections.append({
            "remaining": float(li.get("remaining_amount", 0) or 0),
            "monthly_payment": float(li.get("monthly_payment", 0) or 0),
            "end_year": li.get("end_year"),
        })

    # Project year by year
    forecast = []
    for y in range(projection_years + 1):
        year = current_year + y
        total_assets = 0.0
        for ap in asset_projections:
            if ap["asset_type"] == "financial":
                val = ap["current_value"] * ((1 + ap["annual_return"]) ** y)
            else:
                val = ap["current_value"] * ((1 - ap["depreciation"]) ** y)
            total_assets += max(val, 0)

        total_liabilities = 0.0
        for lp in liability_projections:
            remaining = lp["remaining"] - lp["monthly_payment"] * 12 * y
            if lp["end_year"] and year > lp["end_year"]:
                remaining = 0
            total_liabilities += max(remaining, 0)

        net_worth = total_assets - total_liabilities
        real_net_worth = net_worth / ((1 + inflation_rate) ** y) if y > 0 else net_worth

        forecast.append({
            "year": year,
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "net_worth": round(net_worth, 2),
            "real_net_worth": round(real_net_worth, 2),
        })

    assumptions = {
        "inflation_rate": inflation_rate,
        "projection_years": projection_years,
        "asset_count": len(assets),
        "liability_count": len(liabilities),
    }

    return {
        "history": history_points,
        "forecast": forecast,
        "assumptions": assumptions,
        "summary": None,
    }
