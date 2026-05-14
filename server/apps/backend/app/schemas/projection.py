from pydantic import BaseModel, ConfigDict, field_validator


class ProjectionRequest(BaseModel):
    projection_years: int = 5
    inflation_rate: float = 0.03
    custom_overrides: dict[int, float] | None = None

    @field_validator("projection_years")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (1 <= v <= 30):
            raise ValueError("projection_years 必须在 1-30 之间")
        return v


class ProjectionYearPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    year: int
    total_assets: float
    total_liabilities: float
    net_worth: float
    real_net_worth: float


class ProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    history: list[ProjectionYearPoint]
    forecast: list[ProjectionYearPoint]
    assumptions: dict
    summary: str | None = None
