from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

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


class DeviceCheckUserItem(SnowflakeBase):
    user_id: int
    display_name: str
    username: str | None
    family_name: str
    avatar_color: str
    role: str
    second_factor_type: str | None
    has_passkey: bool
    last_seen_at: datetime


class DeviceCheckResponse(BaseModel):
    trusted: bool
    users: list[DeviceCheckUserItem] = []


class DeviceSelectRequest(BaseModel):
    device_id: str
    user_id: str
    altcha: str | None = None  # Optional; only verified in production

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) > 20:
            raise ValueError("invalid user_id")
        return v


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


class DeviceWebAuthnAuthOptionsRequest(BaseModel):
    """Request challenge for WebAuthn device authentication."""
    device_id: str
    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) > 20:
            raise ValueError("invalid user_id")
        return v


class DeviceWebAuthnAuthOptionsResponse(BaseModel):
    """WebAuthn authentication challenge."""
    options: dict[str, Any]
    challenge: str


class DeviceWebAuthnVerifyRequest(BaseModel):
    """Submit WebAuthn authentication response."""
    device_id: str
    user_id: str
    credential: dict[str, Any]
    challenge: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) > 20:
            raise ValueError("invalid user_id")
        return v


class DeviceWebAuthnVerifyResponse(BaseModel):
    """Result after WebAuthn verification — same shape as DeviceSelectResponse."""
    second_factor_required: bool
    temp_token: str | None = None
    second_factor_type: str | None = None
    display_name: str | None = None
    avatar_color: str | None = None


class DeviceTrustWebAuthnOptionsResponse(BaseModel):
    """Registration options for WebAuthn during device trust."""
    options: dict[str, Any]
    challenge: str


class DeviceTrustWebAuthnRegisterRequest(BaseModel):
    """Complete WebAuthn registration during device trust."""
    credential: dict[str, Any]
    challenge: str
