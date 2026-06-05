from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class DeviceTrustResponse(SnowflakeBase):
    session_id: int
    device_id: str
    device_name: str
    expires_at: datetime


class DeviceSessionResponse(SnowflakeBase):
    session_id: int
    device_id: str | None
    device_name: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    is_current: bool


class DeviceCheckRequest(BaseModel):
    device_id: str


class DeviceCheckUserItem(BaseModel):
    user_id: int
    display_name: str
    avatar_color: str
    role: str
    second_factor_type: str | None
    last_seen_at: datetime


class DeviceCheckResponse(BaseModel):
    trusted: bool
    users: list[DeviceCheckUserItem] = []


class DeviceSelectRequest(BaseModel):
    device_id: str
    user_id: str
    altcha: str


class DeviceSelectResponse(BaseModel):
    second_factor_required: bool
    temp_token: str | None = None
    second_factor_type: str | None = None
    display_name: str | None = None
    avatar_color: str | None = None


class DeviceTrustRequest(BaseModel):
    device_id: str | None = None


class FamilyDeviceResponse(SnowflakeBase):
    session_id: int
    device_id: str | None
    user_id: int
    display_name: str
    avatar_color: str
    device_name: str
    last_seen_at: datetime
    created_at: datetime
    is_current: bool
