"""WebAuthn request/response schemas."""

from typing import Any

from pydantic import BaseModel, field_validator


class WebAuthnRegistrationOptionsRequest(BaseModel):
    """Request to generate registration options for a child passkey."""

    child_id: str

    @field_validator("child_id")
    @classmethod
    def validate_child_id(cls, v: str) -> str:
        # Accept Snowflake ID (numeric string)
        if not v.isdigit():
            raise ValueError("child_id 必须是有效的 Snowflake ID")
        return v


class WebAuthnRegistrationOptionsResponse(BaseModel):
    """Response containing registration options and challenge."""

    options: dict[str, Any]
    challenge: str  # Base64url-encoded challenge


class WebAuthnRegistrationRequest(BaseModel):
    """Request to complete passkey registration for a child."""

    child_id: str
    credential: dict[str, Any]  # PublicKeyCredential from navigator.credentials.create()
    challenge: str  # Challenge from registration options

    @field_validator("child_id")
    @classmethod
    def validate_child_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("child_id 必须是有效的 Snowflake ID")
        return v


class WebAuthnAuthenticationOptionsRequest(BaseModel):
    """Request to generate authentication options for a child passkey."""

    child_id: str

    @field_validator("child_id")
    @classmethod
    def validate_child_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("child_id 必须是有效的 Snowflake ID")
        return v


class WebAuthnAuthenticationOptionsResponse(BaseModel):
    """Response containing authentication options and challenge."""

    options: dict[str, Any]
    challenge: str  # Base64url-encoded challenge


class WebAuthnAuthenticationRequest(BaseModel):
    """Request to complete passkey authentication for a child."""

    child_id: str
    credential: dict[str, Any]  # PublicKeyCredential from navigator.credentials.get()
    challenge: str  # Challenge from authentication options

    @field_validator("child_id")
    @classmethod
    def validate_child_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("child_id 必须是有效的 Snowflake ID")
        return v
