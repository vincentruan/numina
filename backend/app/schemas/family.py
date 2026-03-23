from pydantic import BaseModel

from app.schemas.auth import UserResponse


class FamilyResponse(BaseModel):
    id: str
    name: str
    custom_title: str | None = None
    invite_code: str
    created_by: str
    members: list[UserResponse] = []

    model_config = {"from_attributes": True}

class UpdateFamilyTitleRequest(BaseModel):
    custom_title: str | None

class MemberSummary(BaseModel):
    user: UserResponse
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
