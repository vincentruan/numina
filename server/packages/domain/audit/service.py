"""Audit log purge service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.core.logging import get_logger
from packages.core.settings import settings
from packages.db.session import SessionLocal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("security.audit")


def write_audit_log(
    event_type: str,
    outcome: str,
    user_id: int | str | None = None,
    family_id: int | str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
    db: "Session | None" = None,
) -> None:
    """Append a row to security_audit_logs. Fails silently.

    When db is provided, the entry is added to the caller's session (no commit/close).
    When db is None, a new session is created, committed, and closed.
    """
    if not settings.ENABLE_SECURITY_LOGGING:
        return
    try:
        from packages.db.models.security_audit_log import SecurityAuditLog

        if db is not None:
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
            db.flush()
        else:
            own_db = SessionLocal()
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
                own_db.add(entry)
                own_db.commit()
            finally:
                own_db.close()
    except Exception as exc:
        logger.warning(f"[audit_log] failed to write event={event_type}: {exc}")


def purge_old_audit_logs(retention_days: int = 90) -> int:
    """Delete audit log entries older than retention_days. Returns count deleted."""
    try:
        from datetime import datetime, timedelta, timezone

        from packages.db.models.security_audit_log import SecurityAuditLog

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        db = SessionLocal()
        count = 0
        try:
            count = (
                db.query(SecurityAuditLog)
                .filter(SecurityAuditLog.created_at < cutoff)
                .delete(synchronize_session=False)
            )
            db.commit()
            logger.info(
                f"[audit_log] purged {count} entries older than {retention_days} days"
            )
            write_audit_log(
                event_type="audit_log_purge",
                outcome="success",
                detail=f"purged {count} entries older than {retention_days} days",
            )
        finally:
            db.close()

        return count
    except Exception as exc:
        logger.warning(f"[audit_log] purge failed: {exc}")
        return 0
