"""Device session cleanup functions for the scheduler."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from packages.db.models.device_session import DeviceSession


def cleanup_expired_device_sessions(db: Session) -> int:
    """Mark expired sessions as revoked. Called by scheduler."""
    now = datetime.now(UTC)
    updated = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.expires_at < now,
            DeviceSession.is_revoked.is_(False),
        )
        .update({"is_revoked": True})
    )
    db.commit()
    return updated


def delete_old_revoked_sessions(db: Session) -> int:
    """Hard-delete revoked sessions older than 7 days. Called by scheduler."""
    cutoff = datetime.now(UTC) - timedelta(days=7)
    deleted = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.is_revoked.is_(True),
            or_(DeviceSession.last_seen_at < cutoff, DeviceSession.last_seen_at.is_(None)),
        )
        .delete()
    )
    db.commit()
    return deleted
