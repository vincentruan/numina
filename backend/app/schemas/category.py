from pydantic import BaseModel

from app.schemas.base import SnowflakeBase


class CategoryCreate(BaseModel):
    name: str
    icon: str
    color: str = "#6366F1"
    asset_type: str
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None


class CategoryResponse(SnowflakeBase):
    id: int
    family_id: int | None = None
    name: str
    icon: str
    color: str
    asset_type: str
    sort_order: int
    is_system: bool
