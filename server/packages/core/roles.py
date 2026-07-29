"""User role enum and helpers.

Defines the three roles in the system: owner, member, child.
Uses str Enum for transparent comparison with DB string values.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """System-wide user roles.

    Inherits from str so comparisons with raw DB strings work transparently:
        UserRole.OWNER == "owner"  # True
        User.role == UserRole.CHILD  # works in SQLAlchemy filters
    """

    OWNER = "owner"
    MEMBER = "member"
    CHILD = "child"


def is_child(role: str | UserRole) -> bool:
    """Check if role is child."""
    return role == UserRole.CHILD


def is_owner(role: str | UserRole) -> bool:
    """Check if role is owner."""
    return role == UserRole.OWNER
