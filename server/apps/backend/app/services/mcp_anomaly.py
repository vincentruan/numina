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
                    "5 分钟内工具调用过高",
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
                        "10 分钟内失败率过高",
                        f"{pct}% failure rate in 10 minutes "
                        f"({failures}/{total}, threshold: {int(fail_threshold * 100)}%)",
                    )
                    db.commit()
                except Exception:
                    logger.exception(
                        "[mcp_anomaly] failed to emit high_failure_rate alert family_id=%s",
                        family_id,
                    )
                    db.rollback()

        # Threshold 3: new source IP (first appearance in the lookback window)
        ip_window = now - timedelta(minutes=settings.MCP_ANOMALY_NEW_IP_WINDOW_MINUTES)
        ip_history = now - timedelta(days=settings.MCP_ANOMALY_NEW_IP_HISTORY_DAYS)

        # IPs observed in the recent window
        recent_ips = (
            db.query(MCPAccessLog.family_id, MCPAccessLog.client_ip)
            .filter(
                MCPAccessLog.family_id.in_(family_ids),
                MCPAccessLog.created_at >= ip_window,
                MCPAccessLog.client_ip.isnot(None),
                MCPAccessLog.client_ip != "unknown",
            )
            .group_by(MCPAccessLog.family_id, MCPAccessLog.client_ip)
            .all()
        )

        if recent_ips:
            # IPs already seen earlier in the lookback window — those are "known"
            known_ips = {
                (fam_id, ip)
                for fam_id, ip in db.query(
                    MCPAccessLog.family_id, MCPAccessLog.client_ip
                )
                .filter(
                    MCPAccessLog.family_id.in_(family_ids),
                    MCPAccessLog.created_at >= ip_history,
                    MCPAccessLog.created_at < ip_window,
                    MCPAccessLog.client_ip.isnot(None),
                )
                .group_by(MCPAccessLog.family_id, MCPAccessLog.client_ip)
                .all()
            }

            # New-IP detection needs a baseline: without any prior history a family's
            # very first connection would always look "new" and alert spuriously.
            families_with_history = {
                fam_id
                for (fam_id,) in db.query(MCPAccessLog.family_id)
                .filter(
                    MCPAccessLog.family_id.in_(family_ids),
                    MCPAccessLog.created_at < ip_window,
                )
                .group_by(MCPAccessLog.family_id)
                .all()
            }

            for family_id, client_ip in recent_ips:
                if family_id not in families_with_history:
                    continue
                if (family_id, client_ip) in known_ips:
                    continue
                try:
                    _emit_anomaly_alert(
                        db,
                        family_id,
                        "new_source_ip",
                        # IP in the condition keeps per-IP dedup distinct
                        f"新来源 IP {client_ip}",
                        f"New source IP detected: {client_ip} "
                        f"(not seen in the past {settings.MCP_ANOMALY_NEW_IP_HISTORY_DAYS} days)",
                    )
                    db.commit()
                except Exception:
                    logger.exception(
                        "[mcp_anomaly] failed to emit new_source_ip alert family_id=%s",
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
    condition: str,
    detail: str,
) -> None:
    """Emit an anomaly alert for the family owner.

    *condition* identifies **what happened** and must be stable across scans
    (``new_source_ip`` embeds the IP; the threshold alerts use a fixed phrase).
    *detail* carries the per-scan measurement and goes in the body, never the
    title — a drifting value in the title would break deduplication.

    Alerts are deduplicated per condition: an identical condition stays quiet for
    an hour, while a different one still surfaces even if an earlier alert is
    still unread (``dedup_by_title``).
    """
    from apps.backend.app.services.notification.dispatcher import (
        check_reminder_dedup,
        ensure_reminder,
    )

    title = f"MCP 异常 [{anomaly_type}]: {condition}"
    if check_reminder_dedup(db, family_id, "mcp_anomaly_detected", title, hours=1):
        return

    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": "mcp_anomaly_detected",
            "title": title,
            "body": detail,
            "severity": "warning",
            "template_vars": {
                "anomaly_type": anomaly_type,
            },
        },
        dedup_by_title=True,
    )
    logger.info(
        "[mcp_anomaly] alert emitted family_id=%s type=%s",
        family_id,
        anomaly_type,
    )
