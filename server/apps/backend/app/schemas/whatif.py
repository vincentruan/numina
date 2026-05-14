from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class WhatIfAction(BaseModel):
    action_type: Literal["sell", "buy", "invest", "stop_expense"]
    asset_id: int | None = None
    amount: float | None = None
    annual_return_rate: float = 0.0
    annual_cost: float = 0.0
    liquidation_rate: float = 0.8

    @field_validator("liquidation_rate")
    @classmethod
    def validate_liquidation_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("liquidation_rate 必须在 0-1 之间")
        return v


class WhatIfRequest(BaseModel):
    actions: list[WhatIfAction]
    projection_years: int = 10
    inflation_rate: float = 0.03

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, v: list) -> list:
        if len(v) < 1 or len(v) > 5:
            raise ValueError("actions 数量必须在 1-5 之间")
        return v

    @field_validator("projection_years")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (1 <= v <= 30):
            raise ValueError("projection_years 必须在 1-30 之间")
        return v


class WhatIfYearPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    year: int
    baseline_net_worth: float
    scenario_net_worth: float
    difference: float


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    projection: list[WhatIfYearPoint]
    total_difference: float
    breakeven_year: int | None
    summary: str | None = None
