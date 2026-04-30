from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceTrustResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str
    expires_at: datetime


class DeviceSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_name: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    is_current: bool


class DeviceCheckRequest(BaseModel):
    fingerprint: str


class DeviceCheckResponse(BaseModel):
    trusted: bool
    device_name: str | None = None
    user_id: str | None = None


class DeviceTrustRequest(BaseModel):
    fingerprint: str | None = None  # optional browser fingerprint
