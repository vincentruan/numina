"""AI task request schemas for internal callback endpoints (U9)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class TaskProgressRequest(BaseModel):
    """Request body for progress callback."""

    model_config = ConfigDict(from_attributes=True)

    progress: dict[str, Any]

    @field_validator("progress")
    @classmethod
    def validate_progress_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Limit progress JSON size to prevent abuse."""
        import json
        if len(json.dumps(v)) >= 10000:
            raise ValueError("progress JSON exceeds 10000 bytes")
        return v


class TaskCompleteRequest(BaseModel):
    """Request body for completion callback."""

    model_config = ConfigDict(from_attributes=True)

    result_summary: str | None = None


class TaskFailRequest(BaseModel):
    """Request body for failure callback."""

    model_config = ConfigDict(from_attributes=True)

    error_message: str

    @field_validator("error_message")
    @classmethod
    def truncate_error_message(cls, v: str) -> str:
        """Truncate error message to 500 characters."""
        return v[:500] if len(v) > 500 else v


class TaskHeartbeatRequest(BaseModel):
    """Request body for heartbeat callback."""

    model_config = ConfigDict(from_attributes=True)

    expires_at: datetime | None = None
