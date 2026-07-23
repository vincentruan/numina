from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class WishCreate(BaseModel):
    name: str
    description: str | None = None
    expected_price: Decimal | None = None  # NUMERIC(18,2); str on the wire
    priority: str = "medium"
    category_id: int | None = None
    currency: str = "CNY"
    converts_to_asset: bool = True
    target_date: date | None = None
    monthly_saving: Decimal | None = None
    ignore_debt_warning: bool | None = None  # W5


class WishUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    expected_price: Decimal | None = None
    priority: str | None = None
    status: str | None = None
    category_id: int | None = None
    currency: str | None = None
    converts_to_asset: bool | None = None
    target_date: date | None = None
    monthly_saving: Decimal | None = None
    ignore_debt_warning: bool | None = None  # W5


class WishRealizeRequest(BaseModel):
    purchase_price: float
    purchase_date: date
    category_id: int | None = None


class WishIgnoreDebtWarning(BaseModel):
    """PATCH body for /wishes/{id}/ignore-debt-warning (W5)."""
    ignore: bool


class CategoryInfo(SnowflakeBase):
    id: int
    name: str
    icon: str
    asset_type: str


class WishResponse(SnowflakeBase):
    id: int
    family_id: int
    user_id: int
    name: str
    description: str | None
    expected_price: str | None  # NUMERIC(18,2) Decimal → str (2 decimals), or None
    priority: str
    status: str
    category_id: int | None
    category: CategoryInfo | None
    currency: str = "CNY"
    converts_to_asset: bool
    saved_amount: str  # derived cache; Decimal → str (2 decimals)
    monthly_saving: str  # Decimal → str (2 decimals)
    target_date: date | None
    savings_count: int = 0  # computed (count of wish_savings_log rows)
    ignore_debt_warning: bool
    realized_asset_id: int | None
    fulfilled_at: datetime | None = Field(default=None, description="Timestamp when wish was realized/fulfilled (status became 'realized')")
    created_at: datetime
    updated_at: datetime

    @field_validator("expected_price", "saved_amount", "monthly_saving", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if v is None:
            return None
        return str(Decimal(v).quantize(Decimal("0.01")))
