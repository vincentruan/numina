"""MCP access log statistics aggregation service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.models.mcp_access_log import MCPAccessLog
from apps.backend.app.schemas.mcp_access_log import (
    MCPHourlyBucket,
    MCPIPBreakdown,
    MCPStatsResponse,
    MCPToolBreakdown,
)


def get_mcp_stats(
    family_id: int,
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> MCPStatsResponse:
    """Compute aggregate stats for external MCP tool usage."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        date_from = date_to - timedelta(days=7)

    base_q = db.query(MCPAccessLog).filter(
        MCPAccessLog.family_id == family_id,
        MCPAccessLog.event_type == "tool_call",
        MCPAccessLog.created_at >= date_from,
        MCPAccessLog.created_at <= date_to,
    )

    total = base_q.count()

    # Status counts
    status_counts = dict(
        base_q.with_entities(
            MCPAccessLog.status, func.count(MCPAccessLog.id)
        ).group_by(MCPAccessLog.status).all()
    )
    success_count = status_counts.get("success", 0)
    failure_count = status_counts.get("failure", 0)
    error_count = status_counts.get("error", 0)
    permission_denied_count = status_counts.get("permission_denied", 0)
    success_rate = (success_count / total) if total > 0 else 0.0

    # Tool breakdown
    tool_rows = (
        base_q.with_entities(
            MCPAccessLog.tool_name, func.count(MCPAccessLog.id)
        )
        .filter(MCPAccessLog.tool_name.isnot(None))
        .group_by(MCPAccessLog.tool_name)
        .order_by(func.count(MCPAccessLog.id).desc())
        .all()
    )
    tool_breakdown = [
        MCPToolBreakdown(tool_name=name or "unknown", count=count)
        for name, count in tool_rows
    ]

    # IP breakdown
    ip_rows = (
        base_q.with_entities(
            MCPAccessLog.client_ip,
            func.count(MCPAccessLog.id),
            func.max(MCPAccessLog.user_agent),
        )
        .group_by(MCPAccessLog.client_ip)
        .order_by(func.count(MCPAccessLog.id).desc())
        .all()
    )
    ip_breakdown = [
        MCPIPBreakdown(client_ip=ip, count=count, user_agent=ua)
        for ip, count, ua in ip_rows
    ]

    # Hourly buckets — dialect-aware: PostgreSQL uses to_char, SQLite uses strftime
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        hour_expr = func.to_char(MCPAccessLog.created_at, "YYYY-MM-DD HH24:00")
    else:
        hour_expr = func.strftime("%Y-%m-%d %H:00", MCPAccessLog.created_at)

    hourly_rows = (
        base_q.with_entities(
            hour_expr.label("hour"),
            func.count(MCPAccessLog.id),
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    hourly_buckets = [
        MCPHourlyBucket(hour=str(hour), count=count)
        for hour, count in hourly_rows
    ]

    return MCPStatsResponse(
        total_calls=total,
        success_count=success_count,
        failure_count=failure_count,
        error_count=error_count,
        permission_denied_count=permission_denied_count,
        success_rate=round(success_rate, 4),
        hourly_buckets=hourly_buckets,
        tool_breakdown=tool_breakdown,
        ip_breakdown=ip_breakdown,
    )
