"""Pydantic schemas for MCP external API token management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class MCPTokenResponse(SnowflakeBase):
    """Token metadata — never includes hash or plaintext."""

    token_prefix: str
    token_last4: str
    allow_external: bool
    allow_write: bool
    allowed_tools: list[str] | None = None  # None = all tools available
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_at: datetime

    @field_validator("allowed_tools", mode="before")
    @classmethod
    def _parse_allowed_tools(cls, v):
        """Deserialize JSON text from DB into list[str]."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v


class MCPTokenGenerateResponse(MCPTokenResponse):
    """Returned once at generation/rotation — includes plaintext token."""

    token: str  # plaintext, shown exactly once


class MCPTokenUpdate(BaseModel):
    """PATCH body — all fields optional."""

    allow_external: bool | None = None
    allow_write: bool | None = None
    allowed_tools: list[str] | None = None  # null = reset to all-available
    expires_at: datetime | None = None
