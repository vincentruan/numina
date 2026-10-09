"""Pydantic schemas for MCP access log and statistics."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class MCPAccessLogResponse(SnowflakeBase):
    """Single access log entry."""

    family_id: int
    token_id: int | None
    session_id: str | None
    event_type: str
    tool_name: str | None
    status: str
    duration_ms: int | None
    client_ip: str
    user_agent: str | None
    args_digest: str | None
    error_code: str | None
    created_at: datetime


class MCPAccessLogListResponse(BaseModel):
    """Paginated access log list."""

    items: list[MCPAccessLogResponse]
    total: int
    page: int
    page_size: int


class MCPToolBreakdown(BaseModel):
    tool_name: str
    count: int


class MCPIPBreakdown(BaseModel):
    client_ip: str
    count: int
    user_agent: str | None = None


class MCPHourlyBucket(BaseModel):
    hour: str  # ISO format hour bucket
    count: int


class MCPStatsResponse(BaseModel):
    """Aggregate stats for the MCP token usage."""

    total_calls: int
    success_count: int
    failure_count: int
    error_count: int
    permission_denied_count: int
    success_rate: float
    hourly_buckets: list[MCPHourlyBucket]
    tool_breakdown: list[MCPToolBreakdown]
    ip_breakdown: list[MCPIPBreakdown]
