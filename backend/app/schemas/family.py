from pydantic import BaseModel, field_validator

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

class FamilySettingsUpdate(BaseModel):
    auto_approve_hours: int | None = None
    ai_enabled: bool | None = None

    @field_validator("auto_approve_hours")
    @classmethod
    def check_auto_approve_hours(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 168):
            raise ValueError("自动批准时间必须在 1-168 小时之间")
        return v


class FamilySettingsResponse(BaseModel):
    auto_approve_hours: int
    ai_enabled: bool
    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    user: UserResponse
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
