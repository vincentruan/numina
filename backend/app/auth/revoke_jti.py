"""JTI (JWT ID) revocation management.

Provides database-backed revocation for:
1. Single token revocation (by JTI)
2. User-level revocation (all tokens for a user)

Revocation state persists across server restarts.
"""

import time

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.revoked_token import RevokedToken


def revoke_jti(jti: str, ttl_seconds: float) -> None:
    """Mark a single JTI as revoked, persisted to database."""
    db = SessionLocal()
    try:
        now = time.time()
        expires_at = now + ttl_seconds
        record = RevokedToken(
            jti=jti,
            user_id=None,
            revoked_at=now,
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


def revoke_all_user_tokens(user_id: str | int) -> None:
    """Revoke all tokens for a user, persisted to database."""
    db = SessionLocal()
    try:
        now = time.time()
        # Tokens expire after max refresh token lifetime (7 days by default)
        # Use 8 days to cover edge cases
        expires_at = now + (settings.REFRESH_TOKEN_EXPIRE_DAYS + 1) * 24 * 3600
        record = RevokedToken(
            jti=None,
            user_id=str(user_id),
            revoked_at=now,
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


def _is_jti_revoked(jti: str) -> bool:
    """Check if JTI is revoked, querying database."""
    db = SessionLocal()
    try:
        now = time.time()
        record = db.query(RevokedToken).filter(
            RevokedToken.jti == jti,
            RevokedToken.expires_at > now,
        ).first()
        return record is not None
    finally:
        db.close()


def _is_token_revoked_for_user(user_id: str | int, iat: float) -> bool:
    """Check if user has revoked all tokens before iat."""
    db = SessionLocal()
    try:
        now = time.time()
        # Find user-level revocation record
        record = db.query(RevokedToken).filter(
            RevokedToken.user_id == str(user_id),
            RevokedToken.expires_at > now,
        ).first()
        if record is None:
            return False
        # Token issued before revocation time is revoked
        return iat <= record.revoked_at
    finally:
        db.close()


def cleanup_expired_revoked_tokens(db: Session) -> int:
    """Remove expired revocation records. Called by scheduled job."""
    now = time.time()
    deleted = db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
    db.commit()
    return deleted