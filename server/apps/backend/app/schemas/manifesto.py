"""Pydantic schemas for family manifesto feature."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from apps.backend.app.schemas.base import SnowflakeBase

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ManifestoCreateRequest(BaseModel):
    template_id: str
    title: str = Field(max_length=200)
    body: str
    signing_deadline: datetime | None = None
    trackable_clause_indices: list[int] | None = None


class ManifestoPublishRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    change_type: str = Field(pattern=r"^(minor|major)$")
    trackable_clause_indices: list[int] | None = None


class ManifestoSignRequest(BaseModel):
    signature_data: str | None = None


class ManifestoFeedbackCreateRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ManifestoSignatureItem(SnowflakeBase):
    id: int
    user_id: int
    signature_data: str | None
    signed_at: datetime


class ManifestoVersionItem(SnowflakeBase):
    id: int
    version_number: int
    template_id: str
    title: str
    body: str
    change_type: str
    trackable_clause_indices: list[int] | None
    signed_at: datetime | None
    created_by: int
    created_at: datetime


class ManifestoResponse(SnowflakeBase):
    id: int
    family_id: int
    current_version_id: int | None
    status: str
    signing_deadline: datetime | None
    created_by: int
    created_at: datetime
    current_version: ManifestoVersionItem | None = None
    signatures: list[ManifestoSignatureItem] = []


class ManifestoDashboardSummaryResponse(SnowflakeBase):
    manifesto_id: int
    title: str
    total_members: int
    signed_count: int
    status: str


class ManifestoFeedbackResponse(SnowflakeBase):
    id: int
    user_id: int
    content: str
    is_read: bool
    created_at: datetime


class ManifestoVersionHistoryItem(SnowflakeBase):
    id: int
    version_number: int
    change_type: str
    title: str
    created_by: int
    created_at: datetime


class UnsignedManifestoCheckResponse(SnowflakeBase):
    has_unsigned: bool
    manifesto_id: int | None = None
    title: str | None = None


class ChildManifestoResponse(SnowflakeBase):
    manifesto_id: int
    title: str
    body: str
    template_id: str
    signed: bool
    signer_names: list[str] = []


class ChildTrackableClausesResponse(BaseModel):
    has_trackable: bool
    trackable_clause_indices: list[int] = []
