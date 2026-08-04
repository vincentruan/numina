"""Schemas for family-scoped remote storage backend configuration."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class StorageBackendType(str, Enum):
    GITHUB = "github"
    WEBDAV = "webdav"


# ---------------------------------------------------------------------------
# Config sub-schemas — one per backend type.
# Sent in the ``config`` field of create/update requests.
# ---------------------------------------------------------------------------


class GitHubStorageConfig(BaseModel):
    repo_owner: str
    repo_name: str
    branch: str = "main"
    token: str  # Personal access token with repo scope

    @field_validator("repo_owner", "repo_name", "token")
    @classmethod
    def _non_empty(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v


class WebDAVStorageConfig(BaseModel):
    base_url: str
    username: str
    password: str

    @field_validator("base_url", "username", "password")
    @classmethod
    def _non_empty(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @field_validator("base_url")
    @classmethod
    def _valid_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class StorageBackendCreateRequest(BaseModel):
    backend_type: StorageBackendType
    config: GitHubStorageConfig | WebDAVStorageConfig
    display_name: str | None = None
    is_active: bool = True


class StorageBackendUpdateRequest(BaseModel):
    config: GitHubStorageConfig | WebDAVStorageConfig | None = None
    display_name: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StorageBackendResponse(SnowflakeBase):
    """Public view of a family's storage backend (no credentials exposed)."""

    backend_type: str
    display_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StorageBackendStatusResponse(BaseModel):
    """Lightweight status returned by GET /family/storage/status.

    Used by the frontend to decide which UI state to render.
    """

    configured: bool
    backend_type: str | None = None
    display_name: str | None = None
    is_active: bool = False
