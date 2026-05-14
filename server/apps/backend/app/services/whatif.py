"""What-if 消费模拟计算引擎。"""


def calculate_whatif(
    current_net_worth: float,
    assets: list[dict],
    liabilities: list[dict],
    actions: list[dict],
    projection_years: int = 10,
    inflation_rate: float = 0.03,
) -> dict:
    asset_map = {a["id"]: a for a in assets}
    annual_liability_cost = sum(
        (li.get("monthly_payment") or 0) * 12 for li in liabilities
    )

    # Build baseline annual delta from all assets
    baseline_annual_gain = 0.0
    baseline_annual_loss = 0.0
    for a in assets:
        if a["asset_type"] == "financial":
            baseline_annual_gain += a["current_value"] * a.get("annual_return", 0)
        else:
            baseline_annual_loss += a["current_value"] * a.get("annual_depreciation", 0.1)
            baseline_annual_loss += a.get("annual_maintenance_cost", 0) or 0

    # Build scenario adjustments from actions
    scenario_year0_delta = 0.0  # one-time changes at year 0
    scenario_annual_gain_delta = 0.0
    scenario_annual_loss_delta = 0.0

    for act in actions:
        atype = act["action_type"]
        if atype == "sell":
            asset = asset_map.get(act.get("asset_id"))
            if asset:
                sell_income = asset["current_value"] * act.get("liquidation_rate", 0.8)
                scenario_year0_delta += sell_income
                if asset["asset_type"] == "physical":
                    scenario_annual_loss_delta -= (
                        asset["current_value"] * asset.get("annual_depreciation", 0.1)
                    )
                    scenario_annual_loss_delta -= asset.get("annual_maintenance_cost", 0) or 0
                else:
                    scenario_annual_gain_delta -= (
                        asset["current_value"] * asset.get("annual_return", 0)
                    )
        elif atype == "invest":
            amt = act.get("amount", 0) or 0
            scenario_year0_delta -= amt
            scenario_annual_gain_delta += amt * act.get("annual_return_rate", 0)
        elif atype == "buy":
            amt = act.get("amount", 0) or 0
            scenario_year0_delta -= amt
            scenario_annual_loss_delta += act.get("annual_cost", 0)
        elif atype == "stop_expense":
            asset = asset_map.get(act.get("asset_id"))
            saved = act.get("amount") or (
                asset.get("annual_maintenance_cost", 0) if asset else 0
            )
            scenario_annual_loss_delta -= saved or 0

    # Project year by year
    projection = []
    baseline = current_net_worth
    scenario = current_net_worth + scenario_year0_delta
    breakeven_year = None

    for y in range(projection_years + 1):
        diff = round(scenario - baseline, 2)
        projection.append({
            "year": y,
            "baseline_net_worth": round(baseline, 2),
            "scenario_net_worth": round(scenario, 2),
            "difference": diff,
        })
        if y > 0 and breakeven_year is None and diff > 0:
            breakeven_year = y

        if y < projection_years:
            baseline_delta = baseline_annual_gain - baseline_annual_loss - annual_liability_cost
            baseline += baseline_delta

            scenario_delta = (
                baseline_annual_gain
                + scenario_annual_gain_delta
                - baseline_annual_loss
                - scenario_annual_loss_delta
                - annual_liability_cost
            )
            scenario += scenario_delta

    return {
        "projection": projection,
        "total_difference": projection[-1]["difference"],
        "breakeven_year": breakeven_year,
        "summary": None,
    }
