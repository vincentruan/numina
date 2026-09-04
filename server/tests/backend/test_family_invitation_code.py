"""Tests for family invitation code validation during registration."""

from datetime import UTC, datetime

import pytest

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.schemas.auth import RegisterRequest
from apps.backend.app.services.auth import register


@pytest.fixture
def valid_invitation_code(db):
    """Create a valid unused invitation code for testing."""
    code = FamilyInvitationCode(code="TVLID")
    db.add(code)
    db.commit()
    return code


@pytest.fixture
def used_invitation_code(db):
    """Create an already-used invitation code for testing."""
    code = FamilyInvitationCode(
        code="TUSED",
        is_used=True,
        used_at=datetime.now(UTC),
        used_by_family_id="test-family-id",
        used_by_username="test-user",
    )
    db.add(code)
    db.commit()
    return code


@pytest.fixture
def revoked_invitation_code(db):
    """Create a revoked invitation code for testing."""
    code = FamilyInvitationCode(
        code="TRVOK",
        revoked_at=datetime.now(UTC),
    )
    db.add(code)
    db.commit()
    return code


def test_register_with_valid_invitation_code(db, valid_invitation_code):
    """Registration succeeds with valid unused invitation code."""
    req = RegisterRequest(
        username="newuser",
        password="Password123",
        display_name="New User",
        family_name="New Family",
        family_invitation_code="TVLID",
    )

    result = register(db, req, client_ip="test-ip")

    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.token_type == "bearer"

    # Verify code is marked as used after registration
    db.refresh(valid_invitation_code)
    assert valid_invitation_code.is_used
    assert valid_invitation_code.used_at is not None
    assert valid_invitation_code.used_by_username == "newuser"


def test_register_with_invalid_invitation_code(db):
    """Fails with non-existent invitation code."""
    req = RegisterRequest(
        username="newuser",
        password="Password123",
        display_name="New User",
        family_name="New Family",
        family_invitation_code="ZZZZZ",
    )

    with pytest.raises(AppError) as exc_info:
        register(db, req, client_ip="test-ip")

    assert exc_info.value.code == ErrorCode.FAMILY_INVITATION_CODE_NOT_FOUND


def test_register_with_already_used_code(db, used_invitation_code):
    """Fails with already-used invitation code."""
    req = RegisterRequest(
        username="anotheruser",
        password="Password123",
        display_name="Another User",
        family_name="Another Family",
        family_invitation_code="TUSED",
    )

    with pytest.raises(AppError) as exc_info:
        register(db, req, client_ip="test-ip")

    assert exc_info.value.code == ErrorCode.FAMILY_INVITATION_CODE_ALREADY_USED


def test_register_with_revoked_code(db, revoked_invitation_code):
    """Fails with revoked invitation code."""
    req = RegisterRequest(
        username="newuser",
        password="Password123",
        display_name="New User",
        family_name="New Family",
        family_invitation_code="TRVOK",
    )

    with pytest.raises(AppError) as exc_info:
        register(db, req, client_ip="test-ip")

    assert exc_info.value.code == ErrorCode.FAMILY_INVITATION_CODE_REVOKED


def test_invitation_code_normalized_to_uppercase(db):
    """Lowercase input matches uppercase code."""
    # Create code in uppercase
    code = FamilyInvitationCode(code="TLWLR")
    db.add(code)
    db.commit()

    # Register with lowercase input (schema normalizes to uppercase)
    req = RegisterRequest(
        username="newuser",
        password="Password123",
        display_name="New User",
        family_name="New Family",
        family_invitation_code="tlwlr",  # lowercase input → normalized to "TLWLR"
    )

    result = register(db, req, client_ip="test-ip")

    assert result.access_token is not None
    assert result.refresh_token is not None

    # Verify code was found and marked as used
    db.refresh(code)
    assert code.is_used