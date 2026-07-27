from pydantic import BaseModel, ConfigDict, field_validator

from apps.backend.app.schemas.auth import UserResponse
from apps.backend.app.schemas.base import SnowflakeBase


class FamilyResponse(SnowflakeBase):
    id: int
    name: str
    custom_title: str | None = None
    invite_code: str
    creator_code: str | None = None
    created_by: int
    members: list[UserResponse] = []

class UpdateFamilyTitleRequest(BaseModel):
    custom_title: str | None

class FamilySettingsUpdate(BaseModel):
    auto_approve_hours: int | None = None
    ai_enabled: bool | None = None
    coin_copper_to_silver: int | None = None
    coin_silver_to_gold: int | None = None
    education_reward_enabled: bool | None = None
    coin_to_yuan_rate: int | None = None
    report_auto_generate_enabled: bool | None = None

    @field_validator("auto_approve_hours")
    @classmethod
    def check_auto_approve_hours(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 168):
            raise ValueError("自动批准时间必须在 1-168 小时之间")
        return v

    @field_validator("coin_copper_to_silver", "coin_silver_to_gold")
    @classmethod
    def check_coin_rate(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 100):
            raise ValueError("兑换比例必须在 1-100 之间")
        return v

    @field_validator("coin_to_yuan_rate")
    @classmethod
    def check_coin_to_yuan_rate(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("星币兑换汇率不能为负数")
        return v


class FamilySettingsResponse(BaseModel):
    auto_approve_hours: int
    ai_enabled: bool
    coin_copper_to_silver: int
    coin_silver_to_gold: int
    education_reward_enabled: bool
    coin_to_yuan_rate: int
    report_auto_generate_enabled: bool
    model_config = ConfigDict(from_attributes=True)


class MemberSummary(BaseModel):
    user: UserResponse
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int


class ChildEconomyConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    auto_approve_hours: int
    coin_copper_to_silver: int
    coin_silver_to_gold: int
    education_reward_enabled: bool
    coin_to_yuan_rate: int


class ChildEconomyConfigUpdate(BaseModel):
    auto_approve_hours: int | None = None
    coin_copper_to_silver: int | None = None
    coin_silver_to_gold: int | None = None
    education_reward_enabled: bool | None = None
    coin_to_yuan_rate: int | None = None

    @field_validator("auto_approve_hours")
    @classmethod
    def check_auto_approve_hours(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 168):
            raise ValueError("自动批准时间必须在 1-168 小时之间")
        return v

    @field_validator("coin_copper_to_silver", "coin_silver_to_gold")
    @classmethod
    def check_coin_rate(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 100):
            raise ValueError("兑换比例必须在 1-100 之间")
        return v

    @field_validator("coin_to_yuan_rate")
    @classmethod
    def check_coin_to_yuan_rate(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("星币兑换汇率不能为负数")
        return v
