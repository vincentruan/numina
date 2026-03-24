from pydantic import BaseModel


class CurrencyResponse(BaseModel):
    code: str
    name_zh: str
    name_en: str
    symbol: str
    flag_emoji: str
    is_favorite: bool
    sort_order: int

    model_config = {"from_attributes": True}


class RateResponse(BaseModel):
    rate: float
    fetched_at: str