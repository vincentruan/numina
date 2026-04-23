"""JWT token utilities for Snowflake ID handling.

Centralizes ID-to-string conversions for JWT payloads, eliminating scattered str() calls.
"""

from app.models.user import User


def user_claims(user: User, **extra: object) -> dict[str, object]:
    """Build JWT claims from a User model.

    Converts Snowflake IDs (int) to strings for JWT compatibility.
    Use this instead of manually constructing {"sub": str(user.id), ...}.

    Args:
        user: User model instance
        **extra: Additional claims to merge (e.g. token_version=user.token_version)

    Returns:
        JWT claims dict with stringified IDs and any extra fields

    Examples:
        create_access_token(user_claims(user))
        create_refresh_token(user_claims(user, token_version=user.token_version))
    """
    return {
        "sub": str(user.id),
        "fid": str(user.family_id),
        "role": user.role,
        **extra,
    }


def id_keyed_dict(items: dict[int, any]) -> dict[str, any]:
    """Convert integer keys to strings for JSON serialization.

    Use when building dicts with Snowflake IDs as keys (e.g., {child_id: balance}).
    JSON requires string keys, so this converts {123: value} → {"123": value}.

    Args:
        items: Dict with integer keys

    Returns:
        Dict with stringified keys
    """
    return {str(k): v for k, v in items.items()}


def normalize_user_id(user_id: int | str) -> str:
    """Normalize user_id to string for dict key lookups.

    Use in revocation stores and other dicts keyed by user_id.
    Handles both int (from ORM) and str (from JWT) inputs.

    Args:
        user_id: User ID as int or string

    Returns:
        User ID as string
    """
    return str(user_id)
