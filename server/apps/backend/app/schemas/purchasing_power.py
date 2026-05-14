from pydantic import BaseModel, ConfigDict


class PurchasingPowerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_amount: float
    adjusted_amount: float
    from_year: int
    to_year: int
    cumulative_inflation: float
    annual_avg_inflation: float
    explanation: str
