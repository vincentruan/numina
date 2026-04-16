"""Security audit log service.

Write-only interface for the security_audit_logs table.
Never update or delete rows — this table is append-only.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("security.audit")


def write_audit_log(
    event_type: str,
    outcome: str,
    user_id: str | None = None,
    family_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
) -> None:
    """Append a row to security_audit_logs.

    Fails silently — audit logging must never break the main request flow.
    """
    if not settings.ENABLE_SECURITY_LOGGING:
        return
    try:
        from app.database import SessionLocal
        from app.models.security_audit_log import SecurityAuditLog

        db = SessionLocal()
        try:
            entry = SecurityAuditLog(
                event_type=event_type,
                user_id=user_id,
                family_id=family_id,
                ip_address=ip_address,
                user_agent=user_agent,
                outcome=outcome,
                detail=detail,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"[audit_log] failed to write event={event_type}: {exc}")


def purge_old_audit_logs(retention_days: int = 90) -> int:
    """Delete audit log entries older than retention_days. Returns count deleted."""
    try:
        from datetime import datetime, timedelta
        from app.database import SessionLocal
        from app.models.security_audit_log import SecurityAuditLog

        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        db = SessionLocal()
        try:
            count = db.query(SecurityAuditLog).filter(
                SecurityAuditLog.created_at < cutoff
            ).delete(synchronize_session=False)
            db.commit()
            logger.info(f"[audit_log] purged {count} entries older than {retention_days} days")
            return count
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"[audit_log] purge failed: {exc}")
        return 0
