"""MCP anomaly detection scanner.

Periodically scans recent mcp_access_logs rows and emits alerts when
thresholds are exceeded (frequency spike, high failure rate).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.core.logging import get_logger
from packages.core.settings import settings

logger = get_logger(__name__)


def scan_mcp_anomalies() -> None:
    """Scan recent MCP access logs and emit anomaly alerts.

    Called by the scheduler job every 5 minutes.
    """
    from sqlalchemy import case as sa_case
    from sqlalchemy import func
    from sqlalchemy.orm import Session

    from apps.backend.app.database import SessionLocal
    from apps.backend.app.models.family_mcp_token import FamilyMCPToken
    from apps.backend.app.models.mcp_access_log import MCPAccessLog

    db: Session = SessionLocal()
    try:
        # Find families with active tokens
        active_tokens = (
            db.query(FamilyMCPToken.family_id)
            .filter(FamilyMCPToken.is_active.is_(True), FamilyMCPToken.allow_external.is_(True))
            .all()
        )
        family_ids = [fid for (fid,) in active_tokens]
        if not family_ids:
            return

        now = datetime.now(UTC)

        # Threshold 1: frequency spike (>100 tool calls in 5 minutes)
        freq_threshold = settings.MCP_ANOMALY_FREQUENCY_THRESHOLD
        freq_window = now - timedelta(minutes=5)
        freq_rows = (
            db.query(
                MCPAccessLog.family_id,
                func.count(MCPAccessLog.id).label("call_count"),
            )
            .filter(
                MCPAccessLog.family_id.in_(family_ids),
                MCPAccessLog.event_type == "tool_call",
                MCPAccessLog.created_at >= freq_window,
            )
            .group_by(MCPAccessLog.family_id)
            .having(func.count(MCPAccessLog.id) > freq_threshold)
            .all()
        )
        for family_id, count in freq_rows:
            try:
                _emit_anomaly_alert(
                    db,
                    family_id,
                    "frequency_spike",
                    f"5 分钟内工具调用过高（{count} 次，阈值 {freq_threshold}）",
                    f"{count} tool calls in 5 minutes (threshold: {freq_threshold})",
                )
                db.commit()
            except Exception:
                logger.exception(
                    "[mcp_anomaly] failed to emit frequency_spike alert family_id=%s",
                    family_id,
                )
                db.rollback()

        # Threshold 2: high failure rate (>50% in 10 minutes, min 5 calls)
        fail_threshold = settings.MCP_ANOMALY_FAILURE_RATE_THRESHOLD
        min_calls = settings.MCP_ANOMALY_MIN_CALLS
        fail_window = now - timedelta(minutes=10)
        fail_rows = (
            db.query(
                MCPAccessLog.family_id,
                func.count(MCPAccessLog.id).label("total"),
                func.sum(
                    sa_case(
                        (MCPAccessLog.status != "success", 1),
                        else_=0,
                    )
                ).label("failures"),
            )
            .filter(
                MCPAccessLog.family_id.in_(family_ids),
                MCPAccessLog.event_type == "tool_call",
                MCPAccessLog.created_at >= fail_window,
            )
            .group_by(MCPAccessLog.family_id)
            .having(func.count(MCPAccessLog.id) >= min_calls)
            .all()
        )
        for family_id, total, failures in fail_rows:
            if total > 0 and (failures / total) > fail_threshold:
                pct = round(failures / total * 100)
                try:
                    _emit_anomaly_alert(
                        db,
                        family_id,
                        "high_failure_rate",
                        f"10 分钟内失败率 {pct}%（{failures}/{total}，阈值: {int(fail_threshold * 100)}%）",
                        f"{pct}% failure rate in 10 minutes ({failures}/{total}, threshold: {int(fail_threshold * 100)}%)",
                    )
                    db.commit()
                except Exception:
                    logger.exception(
                        "[mcp_anomaly] failed to emit high_failure_rate alert family_id=%s",
                        family_id,
                    )
                    db.rollback()

        db.commit()
    except Exception:
        logger.exception("[mcp_anomaly] scan failed")
    finally:
        db.close()


def _emit_anomaly_alert(
    db,
    family_id: int,
    anomaly_type: str,
    title_zh: str,
    title_en: str,
) -> None:
    """Emit a deduplicated anomaly alert for the family owner.

    Dedup uses a stable key derived from anomaly_type so that the dynamic
    count/failure detail in the displayed title does not defeat deduplication
    (otherwise each scan's different count would create a new alert).
    """
    from apps.backend.app.services.notification.dispatcher import (
        check_reminder_dedup,
        ensure_reminder,
    )

    # Stable dedup key — varies only by anomaly_type, not by dynamic numbers.
    stable_dedup_title = f"MCP 异常: {anomaly_type}"
    if check_reminder_dedup(db, family_id, "mcp_anomaly_detected", stable_dedup_title, hours=1):
        return

    # User-facing title keeps the dynamic detail for clarity.
    display_title = f"MCP 异常 [{anomaly_type}]: {title_zh}"
    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": "mcp_anomaly_detected",
            "title": display_title,
            "body": title_en,
            "severity": "warning",
            "template_vars": {
                "anomaly_type": anomaly_type,
            },
        },
    )
    logger.info(
        "[mcp_anomaly] alert emitted family_id=%s type=%s",
        family_id,
        anomaly_type,
    )
