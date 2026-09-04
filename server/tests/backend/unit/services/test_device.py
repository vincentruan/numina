"""Unit tests for device service — trust_or_reuse_device."""


from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.services import device as device_service


def _make_family(db) -> Family:
    from apps.backend.app.utils.snowflake import next_id
    fid = next_id()
    family = Family(id=fid, name="TestFamily", invite_code="XXXXXX", created_by=fid)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def _make_user(db, family_id: int, role: str = "owner") -> User:
    import bcrypt

    from apps.backend.app.utils.snowflake import next_id
    user = User(
        id=next_id(),
        family_id=family_id,
        username=f"user_{next_id()}",
        display_name="Test",
        password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_trust_or_reuse_creates_new_when_no_device_id(db):
    """First trust (device_id=None) → new session with generated UUID."""
    family = _make_family(db)
    user = _make_user(db, family.id)
    session, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-new",
        device_name="Mac · Chrome",
        device_id=None,
    )
    assert is_new is True
    assert session.device_id is not None
    assert len(session.device_id) == 36  # UUID v4 format
    assert session.refresh_jti == "jti-new"


def test_trust_or_reuse_reuses_active_session(db):
    """Same device_id + active session → reuse (update jti/last_seen/expires)."""
    family = _make_family(db)
    user = _make_user(db, family.id)
    session1, _ = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-first",
        device_name="Mac · Chrome",
        device_id=None,
    )
    device_id = session1.device_id

    session2, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-second",
        device_name="Mac · Chrome",
        device_id=device_id,
    )
    assert is_new is False
    assert session2.id == session1.id
    assert session2.refresh_jti == "jti-second"
    assert session2.device_id == device_id


def test_trust_or_reuse_creates_new_when_revoked(db):
    """Same device_id but session revoked → new row (audit trail preserved)."""
    family = _make_family(db)
    user = _make_user(db, family.id)
    session1, _ = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-first",
        device_name="Mac · Chrome",
        device_id=None,
    )
    device_id = session1.device_id

    # Revoke the existing session
    session1.is_revoked = True
    db.commit()

    session2, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-revoked",
        device_name="Mac · Chrome",
        device_id=device_id,
    )
    assert is_new is True
    assert session2.id != session1.id
    assert session2.device_id == device_id


def test_trust_or_reuse_creates_new_when_expired(db):
    """Same device_id but session expired → new row."""
    from datetime import UTC, datetime, timedelta
    family = _make_family(db)
    user = _make_user(db, family.id)
    session1, _ = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-first",
        device_name="Mac · Chrome",
        device_id=None,
    )
    device_id = session1.device_id

    # Expire the existing session
    session1.expires_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()

    session2, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-expired",
        device_name="Mac · Chrome",
        device_id=device_id,
    )
    assert is_new is True
    assert session2.id != session1.id
    assert session2.device_id == device_id


def test_trust_or_reuse_partial_unique_constraint(db):
    """Partial unique index prevents duplicate active sessions for same user+device_id."""
    family = _make_family(db)
    user = _make_user(db, family.id)
    session1, _ = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-first",
        device_name="Mac · Chrome",
        device_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert session1.device_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    # Attempting to insert a second active row with same user_id + device_id
    # should raise IntegrityError (caught by trust_or_reuse_device).
    session2, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-duplicate",
        device_name="Mac · Chrome",
        device_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    # Should reuse the existing session (IntegrityError caught → fallback)
    assert is_new is False
    assert session2.id == session1.id


def test_trust_or_reuse_allows_revoked_and_active(db):
    """A revoked session + a new active one with same device_id should coexist."""
    family = _make_family(db)
    user = _make_user(db, family.id)
    session1, _ = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-first",
        device_name="Mac · Chrome",
        device_id="11111111-2222-3333-4444-555555555555",
    )
    # Revoke it
    session1.is_revoked = True
    db.commit()

    # Now trust again with same device_id — should create new active session
    session2, is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user.id,
        family_id=family.id,
        refresh_jti="jti-second",
        device_name="Mac · Chrome",
        device_id="11111111-2222-3333-4444-555555555555",
    )
    assert is_new is True
    assert session2.id != session1.id
    assert session2.device_id == "11111111-2222-3333-4444-555555555555"
