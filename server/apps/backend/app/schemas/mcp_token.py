"""Pydantic schemas for MCP external API token management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class MCPTokenResponse(SnowflakeBase):
    """Token metadata — never includes hash or plaintext."""

    token_prefix: str
    token_last4: str
    allow_external: bool
    allow_write: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_at: datetime


class MCPTokenGenerateResponse(MCPTokenResponse):
    """Returned once at generation/rotation — includes plaintext token."""

    token: str  # plaintext, shown exactly once


class MCPTokenUpdate(BaseModel):
    """PATCH body — all fields optional."""

    allow_external: bool | None = None
    allow_write: bool | None = None
    expires_at: datetime | None = None
