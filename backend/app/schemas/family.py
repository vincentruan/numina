from pydantic import BaseModel

from app.schemas.auth import UserResponse


class FamilyResponse(BaseModel):
    id: str
    name: str
    invite_code: str
    created_by: str
    members: list[UserResponse] = []

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    user: UserResponse
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
