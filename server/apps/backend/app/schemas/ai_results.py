"""Response schemas for AI capability result endpoints.

All schemas inherit from SnowflakeBase to ensure bigint IDs are
serialized as strings in JSON output, preventing JavaScript precision loss.
"""

from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class AllocationDriftResultResponse(SnowflakeBase):
    """Response schema for allocation drift analysis result."""

    id: int
    family_id: int
    has_significant_drift: bool
    narrative: str | None = None
    drifts_json: list | None = None
    generated_at: datetime


class LiabilityResultResponse(SnowflakeBase):
    """Response schema for liability advice result."""

    id: int
    family_id: int
    has_liabilities: bool
    total_remaining: float | None = None
    total_monthly_payment: float | None = None
    liability_count: int | None = None
    narrative: str | None = None
    recommended_strategy: str | None = None
    strategies_json: list | None = None
    generated_at: datetime


class AllocationDriftResultPayload(BaseModel):
    """Payload for successful allocation drift result response."""

    has_result: bool = True
    has_significant_drift: bool
    narrative: str | None = None
    drifts: list | None = None
    generated_at: str


class NoResultPayload(BaseModel):
    """Payload when no result exists."""

    has_result: bool = False


class LiabilityResultPayload(BaseModel):
    """Payload for successful liability result response."""

    has_result: bool = True
    has_liabilities: bool
    total_remaining: float | None = None
    total_monthly_payment: float | None = None
    liability_count: int | None = None
    narrative: str | None = None
    recommended_strategy: str | None = None
    strategies: list | None = None
    generated_at: str