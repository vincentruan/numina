"""Tests for JTI revocation persistence across server restarts."""

import time
from unittest.mock import patch

import packages.security.revoke_jti as revoke_module
from apps.backend.app.auth.revoke_jti import (
    _is_jti_revoked,
    _is_token_revoked_for_user,
    cleanup_expired_revoked_tokens,
    revoke_all_user_tokens,
    revoke_jti,
    revoke_jti_atomic,
)
from apps.backend.app.models.revoked_token import RevokedToken


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


def test_revoke_jti_atomic_first_call_wins(db):
    """revoke_jti_atomic() returns True when the JTI is not yet revoked."""
    jti = "atomic-jti-new"
    ttl = 3600

    db.query(RevokedToken).filter_by(jti=jti).delete()
    db.commit()

    with patch.object(revoke_module, "SessionLocal", return_value=db):
        result = revoke_jti_atomic(jti, ttl)

    assert result is True
    record = db.query(RevokedToken).filter_by(jti=jti).first()
    assert record is not None
    assert record.jti == jti


def test_revoke_jti_atomic_second_call_loses(db):
    """revoke_jti_atomic() returns False when the JTI is already revoked."""
    jti = "atomic-jti-dup"
    ttl = 3600

    db.query(RevokedToken).filter_by(jti=jti).delete()
    db.commit()

    with patch.object(revoke_module, "SessionLocal", return_value=db):
        first = revoke_jti_atomic(jti, ttl)
        second = revoke_jti_atomic(jti, ttl)

    assert first is True
    assert second is False


def test_refresh_token_replay_rejected_service_layer(db):
    """Service-layer test: refresh_token() rejects a replayed token via revoke_jti_atomic.

    Uses the db fixture directly (bypassing the SAVEPOINT-restart limitation of
    the HTTP test client) to verify that the second call to revoke_jti_atomic
    returns False and raises AUTH_REFRESH_FAILED.
    """
    from apps.backend.app.auth.deps import create_refresh_token
    from apps.backend.app.auth.jwt_utils import user_claims
    from apps.backend.app.errors import AppError, ErrorCode
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User
    from apps.backend.app.services.auth import refresh_token as svc_refresh_token
    from apps.backend.app.utils.snowflake import next_id

    # Create a minimal family + user
    family = Family(id=next_id(), name="Replay SVC Family", created_by=next_id())
    db.add(family)
    db.commit()

    user = User(
        id=next_id(),
        family_id=family.id,
        username="replay_svc_user",
        display_name="Replay SVC",
        password_hash="x",
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Issue a refresh token
    tok = create_refresh_token(user_claims(user, token_version=user.token_version))

    # Wrap db so that close() is a no-op — revoke_jti_atomic calls db.close()
    # in its finally block; closing the shared test session detaches ORM objects.
    class _NoClose:
        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(db, name)

        def __setattr__(self, name, value):
            setattr(db, name, value)

    no_close_db = _NoClose()

    # First call: should succeed — revoke_jti_atomic wins the race
    with patch.object(revoke_module, "SessionLocal", return_value=no_close_db):
        result1 = svc_refresh_token(db, tok)
    assert result1.refresh_token != tok  # new token issued

    # Second call with the original token: revoke_jti_atomic should return False
    with patch.object(revoke_module, "SessionLocal", return_value=no_close_db):
        try:
            svc_refresh_token(db, tok)
            raise AssertionError("Expected AUTH_REFRESH_FAILED but no error was raised")
        except AppError as exc:
            assert exc.code == ErrorCode.AUTH_REFRESH_FAILED
