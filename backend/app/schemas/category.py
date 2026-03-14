from pydantic import BaseModel


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


class CategoryResponse(BaseModel):
    id: str
    family_id: str | None = None
    name: str
    icon: str
    color: str
    asset_type: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}
