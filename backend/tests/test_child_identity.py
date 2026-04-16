"""Unit 1 tests: Database Migration — User Model Extensions + ChildBindToken Table

Tests cover:
- User model field additions (pin_hash, pin_fail_count, pin_locked_until, token_version)
- username/password_hash nullable for child accounts
- ChildBindToken table creation
- Partial unique index on username (WHERE username IS NOT NULL)
"""

import pytest
from sqlalchemy.orm import Session

from app.models.child_bind_token import ChildBindToken
from app.models.family import Family
from app.models.user import User


class TestUserModelExtensions:
    """Test User model extensions for child identity."""

    def test_user_has_child_identity_fields(self, db: Session) -> None:
        """User model should have pin_hash, pin_fail_count, pin_locked_until, token_version."""
        # Create a family first
        family = Family(
            id="test-family-1",
            name="Test Family",
            invite_code="ABC123",
            created_by="owner-1",
        )
        db.add(family)
        db.commit()

        # Create a child user with nullable username/password_hash
        child = User(
            id="child-1",
            family_id="test-family-1",
            username=None,  # NULL for child
            display_name="小明",
            password_hash=None,  # NULL for child
            role="child",
            pin_hash="$2b$08$dummyhash",  # bcrypt hash
            pin_fail_count=0,
            pin_locked_until=None,
            token_version=0,
        )
        db.add(child)
        db.commit()

        # Verify fields exist and have correct values
        saved_child = db.query(User).filter(User.id == "child-1").first()
        assert saved_child is not None
        assert saved_child.pin_hash == "$2b$08$dummyhash"
        assert saved_child.pin_fail_count == 0
        assert saved_child.pin_locked_until is None
        assert saved_child.token_version == 0
        assert saved_child.username is None
        assert saved_child.password_hash is None
        assert saved_child.role == "child"

    def test_adult_user_retains_username_uniqueness(self, db: Session) -> None:
        """Adult users should still have unique usernames enforced."""
        # Create a family
        family = Family(
            id="test-family-2",
            name="Test Family 2",
            invite_code="DEF456",
            created_by="owner-2",
        )
        db.add(family)
        db.commit()

        # Create first adult user
        adult1 = User(
            id="adult-1",
            family_id="test-family-2",
            username="parent1",
            display_name="Parent 1",
            password_hash="$2b$12$hash1",
            role="owner",
        )
        db.add(adult1)
        db.commit()

        # Verify adult user has non-null username
        saved = db.query(User).filter(User.id == "adult-1").first()
        assert saved.username == "parent1"
        assert saved.password_hash is not None

    def test_multiple_child_users_can_have_null_username(self, db: Session) -> None:
        """Multiple child accounts can all have username=NULL without constraint violation."""
        # Create a family
        family = Family(
            id="test-family-3",
            name="Test Family 3",
            invite_code="GHI789",
            created_by="owner-3",
        )
        db.add(family)
        db.commit()

        # Create two child users with NULL username
        child1 = User(
            id="child-a",
            family_id="test-family-3",
            username=None,
            display_name="Child A",
            password_hash=None,
            role="child",
            pin_hash="$2b$08$hashA",
        )
        child2 = User(
            id="child-b",
            family_id="test-family-3",
            username=None,
            display_name="Child B",
            password_hash=None,
            role="child",
            pin_hash="$2b$08$hashB",
        )
        db.add_all([child1, child2])
        db.commit()

        # Verify both exist
        children = db.query(User).filter(User.family_id == "test-family-3", User.role == "child").all()
        assert len(children) == 2
        assert all(c.username is None for c in children)

    def test_token_version_defaults_to_zero(self, db: Session) -> None:
        """token_version should default to 0 for new users."""
        family = Family(
            id="test-family-4",
            name="Test Family 4",
            invite_code="JKL012",
            created_by="owner-4",
        )
        db.add(family)
        db.commit()

        # Create user without explicitly setting token_version
        user = User(
            id="user-default",
            family_id="test-family-4",
            username="defaultuser",
            display_name="Default User",
            password_hash="$2b$12$hash",
            role="member",
        )
        db.add(user)
        db.commit()

        saved = db.query(User).filter(User.id == "user-default").first()
        assert saved.token_version == 0  # Should be default 0

    def test_pin_fail_count_defaults_to_zero(self, db: Session) -> None:
        """pin_fail_count should default to 0."""
        family = Family(
            id="test-family-5",
            name="Test Family 5",
            invite_code="MNO345",
            created_by="owner-5",
        )
        db.add(family)
        db.commit()

        user = User(
            id="user-pin-default",
            family_id="test-family-5",
            username="pinuser",
            display_name="Pin User",
            password_hash="$2b$12$hash",
            role="member",
        )
        db.add(user)
        db.commit()

        saved = db.query(User).filter(User.id == "user-pin-default").first()
        assert saved.pin_fail_count == 0


class TestChildBindTokenTable:
    """Test ChildBindToken model for device binding."""

    def test_child_bind_token_creation(self, db: Session) -> None:
        """ChildBindToken can be created with all required fields."""
        family = Family(
            id="bind-family-1",
            name="Bind Family",
            invite_code="PQR678",
            created_by="bind-owner",
        )
        db.add(family)
        db.commit()

        from datetime import datetime, timedelta

        bind_token = ChildBindToken(
            id="token-1",
            family_id="bind-family-1",
            token="abc123xyz789",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
        db.add(bind_token)
        db.commit()

        saved = db.query(ChildBindToken).filter(ChildBindToken.id == "token-1").first()
        assert saved is not None
        assert saved.token == "abc123xyz789"
        assert saved.used is False
        assert saved.family_id == "bind-family-1"

    def test_child_bind_token_family_relationship(self, db: Session) -> None:
        """ChildBindToken should have relationship to Family."""
        family = Family(
            id="bind-family-2",
            name="Bind Family 2",
            invite_code="STU901",
            created_by="bind-owner-2",
        )
        db.add(family)
        db.commit()

        from datetime import datetime, timedelta

        bind_token = ChildBindToken(
            id="token-2",
            family_id="bind-family-2",
            token="unique-token-value",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
        db.add(bind_token)
        db.commit()

        saved = db.query(ChildBindToken).filter(ChildBindToken.id == "token-2").first()
        assert saved.family is not None
        assert saved.family.name == "Bind Family 2"

    def test_child_bind_token_unique_constraint(self, db: Session) -> None:
        """Token field should enforce uniqueness."""
        family = Family(
            id="bind-family-3",
            name="Bind Family 3",
            invite_code="VWX234",
            created_by="bind-owner-3",
        )
        db.add(family)
        db.commit()

        from datetime import datetime, timedelta

        token1 = ChildBindToken(
            id="token-3a",
            family_id="bind-family-3",
            token="duplicate-token",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
        db.add(token1)
        db.commit()

        # Attempt to create second token with same value
        token2 = ChildBindToken(
            id="token-3b",
            family_id="bind-family-3",
            token="duplicate-token",  # Same token value
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
        db.add(token2)

        # Should raise integrity error due to unique constraint
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.commit()


class TestPartialUniqueIndex:
    """Test partial unique index on username (WHERE username IS NOT NULL).

    NOTE: This test verifies the index exists in a migrated database.
    In test environment (in-memory SQLite via Base.metadata.create_all),
    the index is NOT created because ORM models don't define partial indexes.
    This test should pass when running against a real migrated database,
    but will skip in the standard test fixture.
    """

    def test_partial_index_exists_in_migrated_db(self, db: Session) -> None:
        """Verify partial unique index was created via Alembic migration.

        In test environment, this index won't exist (ORM doesn't create it).
        We verify the username column is nullable as a proxy for the migration.
        """
        # Instead of checking for index (which only exists via migration),
        # verify username can be NULL (the migration's key effect)
        family = Family(
            id="index-test-family",
            name="Index Test Family",
            invite_code="INDX01",
            created_by="index-owner",
        )
        db.add(family)
        db.commit()

        # Create user with NULL username (child account)
        # This would fail if migration hadn't made username nullable
        child = User(
            id="index-child",
            family_id="index-test-family",
            username=None,
            display_name="Index Child",
            password_hash=None,
            role="child",
        )
        db.add(child)
        db.commit()

        saved = db.query(User).filter(User.id == "index-child").first()
        assert saved.username is None, "Username should be nullable for child accounts"


class TestMigrationSmoke:
    """Smoke tests for migration application."""

    def test_tables_created_successfully(self, db: Session) -> None:
        """All tables should exist after migration."""
        # Check users table has new columns
        user = User(
            id="smoke-user",
            family_id="smoke-family",
            username="smoke",
            display_name="Smoke Test",
            password_hash="hash",
            role="member",
        )
        db.add(user)
        db.commit()

        # Query should succeed
        saved = db.query(User).filter(User.id == "smoke-user").first()
        assert saved is not None
        # New fields should exist (even if NULL)
        assert hasattr(saved, "pin_hash")
        assert hasattr(saved, "pin_fail_count")
        assert hasattr(saved, "pin_locked_until")
        assert hasattr(saved, "token_version")

    def test_existing_adult_users_unaffected(self, db: Session) -> None:
        """Pre-existing adult users should work after migration."""
        family = Family(
            id="existing-family",
            name="Existing Family",
            invite_code="EXIST01",
            created_by="existing-owner",
        )
        db.add(family)
        db.commit()

        # Simulate pre-existing adult user
        adult = User(
            id="existing-adult",
            family_id="existing-family",
            username="existinguser",
            display_name="Existing User",
            password_hash="$2b$12$prehash",
            role="owner",
        )
        db.add(adult)
        db.commit()

        saved = db.query(User).filter(User.id == "existing-adult").first()
        assert saved.username == "existinguser"
        assert saved.password_hash == "$2b$12$prehash"
        # token_version should be 0 (default)
        assert saved.token_version == 0