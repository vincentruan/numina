"""Schemas for family-scoped remote storage backend configuration."""

import ipaddress
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, model_validator

from apps.backend.app.schemas.base import SnowflakeBase


class StorageBackendType(StrEnum):
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
        # SSRF guard: reject loopback, link-local, and private RFC 1918 ranges.
        # Accepts public hostnames and cloud-provider FQDNs only.
        try:
            parsed = urlparse(v)
            hostname = parsed.hostname or ""
            if not hostname:
                raise ValueError("base_url must include a hostname")
            # Resolve literal IP addresses against private ranges
            try:
                addr = ipaddress.ip_address(hostname)
                if addr.is_loopback or addr.is_private or addr.is_link_local:
                    raise ValueError(
                        "base_url must not point to a private or loopback address"
                    )
            except ValueError as exc:
                if "private" in str(exc) or "loopback" in str(exc):
                    raise
                # Not an IP literal — treat as hostname.
                # Reject well-known internal hostnames.
                lower = hostname.lower()
                if lower in (
                    "localhost",
                    "127.0.0.1",
                    "0.0.0.0",
                    "metadata.google.internal",
                ) or lower.endswith(".internal"):
                    raise ValueError(
                        "base_url must not point to a private or loopback address"
                    ) from exc
        except ValueError as exc:
            if "base_url" in str(exc) or "private" in str(exc) or "loopback" in str(exc):
                raise exc
            raise ValueError(f"Invalid base_url: {exc}") from exc
        return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


def _validate_config_for_type(
    backend_type: StorageBackendType,
    config: GitHubStorageConfig | WebDAVStorageConfig,
) -> None:
    expected_type: type = {
        StorageBackendType.GITHUB: GitHubStorageConfig,
        StorageBackendType.WEBDAV: WebDAVStorageConfig,
    }[backend_type]
    if not isinstance(config, expected_type):
        raise ValueError(
            f"backend_type '{backend_type.value}' requires "
            f"{expected_type.__name__}, got {type(config).__name__}"
        )


class StorageBackendCreateRequest(BaseModel):
    backend_type: StorageBackendType
    config: GitHubStorageConfig | WebDAVStorageConfig
    display_name: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _config_matches_type(self) -> "StorageBackendCreateRequest":
        _validate_config_for_type(self.backend_type, self.config)
        return self


class StorageBackendUpdateRequest(BaseModel):
    config: GitHubStorageConfig | WebDAVStorageConfig | None = None
    display_name: str | None = None
    is_active: bool | None = None

    # backend_type is not accepted on update — type consistency is enforced
    # by the service layer when config changes.  Do not add backend_type
    # here without also wiring _validate_config_for_type in the service.


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StorageBackendResponse(SnowflakeBase):
    """Public view of a family's storage backend (no credentials exposed)."""

    id: int
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
