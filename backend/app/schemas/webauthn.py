"""WebAuthn request/response schemas."""

from typing import Any

from pydantic import BaseModel


class WebAuthnRegistrationOptionsRequest(BaseModel):
    child_id: str


class WebAuthnRegistrationOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge: str  # Base64url-encoded challenge


class WebAuthnRegistrationRequest(BaseModel):
    child_id: str
    credential: dict[str, Any]  # PublicKeyCredential from navigator.credentials.create()
    challenge: str  # Challenge from registration options


class WebAuthnAuthenticationOptionsRequest(BaseModel):
    child_id: str


class WebAuthnAuthenticationOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge: str  # Base64url-encoded challenge


class WebAuthnAuthenticationRequest(BaseModel):
    child_id: str
    credential: dict[str, Any]  # PublicKeyCredential from navigator.credentials.get()
    challenge: str  # Challenge from authentication options
