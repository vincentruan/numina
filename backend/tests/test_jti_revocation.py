"""Tests for JTI revocation persistence across server restarts."""

import time
from unittest.mock import patch

from app.auth import revoke_jti as revoke_module
from app.auth.revoke_jti import (
    revoke_jti,
    revoke_all_user_tokens,
    _is_jti_revoked,
    _is_token_revoked_for_user,
    cleanup_expired_revoked_tokens,
)
from app.models.revoked_token import RevokedToken


def test_revoke_jti_stores_in_database(db):
    """revoke_jti() creates a RevokedToken record in database."""
    jti = "test-jti-123"
    ttl = 3600  # 1 hour

    # Clear any existing records
    db.query(RevokedToken).filter_by(jti=jti).delete()
    db.commit()

    # Mock SessionLocal to return test fixture's db (same in-memory DB)
    with patch.object(revoke_module, 'SessionLocal', return_value=db):
        revoke_jti(jti, ttl)

    # Verify it's in the database
    record = db.query(RevokedToken).filter_by(jti=jti).first()
    assert record is not None
    assert record.jti == jti
    assert record.expires_at > time.time()


def test_is_jti_revoked_queries_database(db):
    """_is_jti_revoked() queries database, not in-memory dict."""
    jti = "test-jti-456"
    ttl = 3600

    # Clear database
    db.query(RevokedToken).delete()
    db.commit()

    # Should not be revoked initially
    with patch.object(revoke_module, 'SessionLocal', return_value=db):
        assert not _is_jti_revoked(jti)

        # Revoke via actual function
        revoke_jti(jti, ttl)

        # Should be revoked now (database lookup)
        assert _is_jti_revoked(jti)


def test_revoke_all_user_tokens_stores_in_database(db):
    """revoke_all_user_tokens() creates a RevokedToken record."""
    user_id = "test-user-789"

    # Clear database
    db.query(RevokedToken).filter_by(user_id=user_id).delete()
    db.commit()

    # Mock SessionLocal to return test fixture's db
    with patch.object(revoke_module, 'SessionLocal', return_value=db):
        revoke_all_user_tokens(user_id)

    # Verify database record
    record = db.query(RevokedToken).filter_by(user_id=user_id).first()
    assert record is not None
    assert record.user_id == user_id
    assert record.revoked_at > 0


def test_is_token_revoked_for_user_queries_database(db):
    """_is_token_revoked_for_user() queries database correctly."""
    user_id = "test-user-revocation"
    token_iat_old = time.time() - 100  # Token issued 100 seconds ago
    token_iat_new = time.time() + 100  # Token issued 100 seconds in future (simulated)

    # Clear database
    db.query(RevokedToken).filter_by(user_id=user_id).delete()
    db.commit()

    with patch.object(revoke_module, 'SessionLocal', return_value=db):
        # No revocation - neither token should be revoked
        assert not _is_token_revoked_for_user(user_id, token_iat_old)
        assert not _is_token_revoked_for_user(user_id, token_iat_new)

        # Revoke all tokens for user
        revoke_all_user_tokens(user_id)

        # Old token (iat before revocation) should be revoked
        assert _is_token_revoked_for_user(user_id, token_iat_old)

        # New token (iat after revocation) should not be revoked
        assert not _is_token_revoked_for_user(user_id, token_iat_new)


def test_cleanup_expired_revoked_tokens(db):
    """cleanup_expired_revoked_tokens() removes expired records."""
    # Insert an expired record
    expired = RevokedToken(
        jti="expired-jti",
        revoked_at=time.time() - 7200,
        expires_at=time.time() - 3600,  # Expired 1 hour ago
    )
    db.add(expired)
    db.commit()

    # Run cleanup using actual function (takes db as parameter)
    deleted = cleanup_expired_revoked_tokens(db)

    # Should be removed
    assert deleted == 1
    assert db.query(RevokedToken).filter_by(jti="expired-jti").first() is None