import pytest
from datetime import datetime, timedelta

from app.models.device_session import DeviceSession
from app.models.user import User
from app.models.family import Family
from app.services import device as device_service


def test_device_session_model_exists(db):
    """DeviceSession table is created and can be queried."""
    count = db.query(DeviceSession).count()
    assert count == 0


def _make_family(db) -> Family:
    from app.utils.snowflake import next_id
    fid = next_id()
    family = Family(id=fid, name="TestFamily", invite_code="XXXXXX", created_by=fid)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def _make_user(db, family_id: int, role: str = "owner") -> User:
    import bcrypt
    from app.utils.snowflake import next_id
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


def test_create_device_session(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="test-jti-1", device_name="iPhone · Safari"
    )
    assert session.refresh_jti == "test-jti-1"
    assert session.device_name == "iPhone · Safari"
    assert not session.is_revoked
    assert session.expires_at > datetime.utcnow() + timedelta(days=29)


def test_list_device_sessions(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-a", device_name="iPhone · Safari"
    )
    device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-b", device_name="Android · Chrome"
    )
    sessions = device_service.list_device_sessions(db, user_id=user.id)
    assert len(sessions) == 2


def test_revoke_device_session(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-revoke", device_name="iPad · Safari"
    )
    device_service.revoke_device_session(db, device_id=session.id, user_id=user.id)
    db.refresh(session)
    assert session.is_revoked


def test_revoke_device_session_wrong_user(db):
    from app.errors import AppError
    family = _make_family(db)
    user1 = _make_user(db, family.id)
    user2 = _make_user(db, family.id, role="member")
    session = device_service.create_device_session(
        db, user_id=user1.id, family_id=family.id,
        refresh_jti="jti-other", device_name="Mac · Chrome"
    )
    with pytest.raises(AppError):
        device_service.revoke_device_session(db, device_id=session.id, user_id=user2.id)


def test_rotate_device_session_jti(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="old-jti", device_name="iPhone · Safari"
    )
    device_service.rotate_device_session_jti(db, old_jti="old-jti", new_jti="new-jti")
    db.refresh(session)
    assert session.refresh_jti == "new-jti"
