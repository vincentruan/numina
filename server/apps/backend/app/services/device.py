"""Device session service — trust, list, revoke, rotate."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.user import User


def create_device_session(
    db: Session,
    *,
    user_id: int,
    family_id: int,
    refresh_jti: str,
    device_name: str,
    browser_fingerprint: str | None = None,
) -> DeviceSession:
    """Create a new trusted device session (30-day expiry)."""
    now = datetime.utcnow()
    session = DeviceSession(
        user_id=user_id,
        family_id=family_id,
        refresh_jti=refresh_jti,
        device_name=device_name,
        browser_fingerprint=browser_fingerprint,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
        is_revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def trust_or_reuse_device(
    db: Session,
    *,
    user_id: int,
    family_id: int,
    refresh_jti: str,
    device_name: str,
    device_id: str | None,
) -> tuple[DeviceSession, bool]:
    """Trust device: reuse active session if same user+device_id, else create new.

    Returns (session, is_new). is_new=False means an existing session was reused.
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(days=30)

    if device_id:
        existing = (
            db.query(DeviceSession)
            .filter(
                DeviceSession.user_id == user_id,
                DeviceSession.device_id == device_id,
                DeviceSession.is_revoked.is_(False),
                DeviceSession.expires_at > now,
            )
            .first()
        )
        if existing:
            existing.refresh_jti = refresh_jti
            existing.device_name = device_name
            existing.last_seen_at = now
            existing.expires_at = expires_at
            db.commit()
            db.refresh(existing)
            return existing, False

    new_device_id = device_id or str(uuid.uuid4())
    session = DeviceSession(
        user_id=user_id,
        family_id=family_id,
        refresh_jti=refresh_jti,
        device_name=device_name,
        device_id=new_device_id,
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, True


def list_device_sessions(db: Session, *, user_id: int) -> list[DeviceSession]:
    """Return active (non-revoked, non-expired) device sessions for a user."""
    now = datetime.utcnow()
    return (
        db.query(DeviceSession)
        .filter(
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .order_by(DeviceSession.last_seen_at.desc())
        .all()
    )


def revoke_device_session(db: Session, *, device_id: int, user_id: int) -> DeviceSession:
    """Revoke a device session. Raises AUTH_DEVICE_NOT_FOUND if not owned by user."""
    session = db.query(DeviceSession).filter(
        DeviceSession.id == device_id,
        DeviceSession.user_id == user_id,
        DeviceSession.is_revoked.is_(False),
    ).first()
    if session is None:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)
    session.is_revoked = True
    db.commit()
    db.refresh(session)
    return session


def revoke_all_device_sessions(db: Session, *, user_id: int) -> list[str]:
    """Revoke all active device sessions for a user. Returns list of revoked JTIs."""
    now = datetime.utcnow()
    sessions = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .all()
    )
    jtis = []
    for s in sessions:
        s.is_revoked = True
        jtis.append(s.refresh_jti)
    db.commit()
    return jtis


def rotate_device_session_jti(db: Session, *, old_jti: str, new_jti: str) -> DeviceSession | None:
    """Update refresh_jti after token rotation. Returns None if no matching session."""
    session = db.query(DeviceSession).filter(
        DeviceSession.refresh_jti == old_jti,
        DeviceSession.is_revoked.is_(False),
    ).first()
    if session is None:
        return None
    session.refresh_jti = new_jti
    session.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def get_device_session_by_jti(db: Session, *, jti: str) -> DeviceSession | None:
    """Look up an active device session by its current refresh JTI."""
    now = datetime.utcnow()
    return db.query(DeviceSession).filter(
        DeviceSession.refresh_jti == jti,
        DeviceSession.is_revoked.is_(False),
        DeviceSession.expires_at > now,
    ).first()


def cleanup_expired_device_sessions(db: Session) -> int:
    """Mark expired sessions as revoked. Called by scheduler."""
    now = datetime.utcnow()
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


def list_family_device_sessions(
    db: Session,
    *,
    family_id: int,
    current_user_id: int,
    current_refresh_jti: str | None,
) -> list[dict]:
    """Return active device sessions for all family members except the caller.

    Each entry is a dict merging DeviceSession fields with the owning User's
    display_name and avatar_color, plus an is_current flag.
    """
    now = datetime.utcnow()
    rows = (
        db.query(DeviceSession, User)
        .join(User, DeviceSession.user_id == User.id)
        .filter(
            DeviceSession.family_id == family_id,
            DeviceSession.user_id != current_user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .order_by(DeviceSession.last_seen_at.desc())
        .all()
    )
    result = []
    for session, user in rows:
        result.append(
            {
                "session_id": session.id,
                "device_id": session.device_id,
                "user_id": session.user_id,
                "display_name": user.display_name,
                "avatar_color": user.avatar_color,
                "device_name": session.device_name,
                "last_seen_at": session.last_seen_at,
                "created_at": session.created_at,
                "is_current": session.refresh_jti == current_refresh_jti,
            }
        )
    return result


def delete_old_revoked_sessions(db: Session) -> int:
    """Hard-delete revoked sessions older than 7 days. Called by scheduler."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    deleted = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.is_revoked.is_(True),
            DeviceSession.last_seen_at < cutoff,
        )
        .delete()
    )
    db.commit()
    return deleted
