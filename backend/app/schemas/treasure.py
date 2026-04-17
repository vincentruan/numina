from datetime import date

from pydantic import BaseModel, ConfigDict


class TreasureItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    image_url: str | None
    purchase_date: date | None
    coins_spent: int | None  # 花费的星星币数
