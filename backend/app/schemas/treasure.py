from datetime import date

from app.schemas.base import SnowflakeBase


class TreasureItem(SnowflakeBase):
    id: int
    name: str
    image_url: str | None
    purchase_date: date | None
    coins_spent: int | None  # 花费的星星币数
