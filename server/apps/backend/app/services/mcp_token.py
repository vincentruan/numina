"""MCP external API token lifecycle: generate, verify, rotate, update access."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family_mcp_token import FamilyMCPToken
from apps.backend.app.models.user import User
from packages.core.logging import get_logger
from packages.core.roles import UserRole
from packages.core.snowflake import next_id

logger = get_logger(__name__)

_TOKEN_PREFIX = "mcp_"
_TOKEN_RANDOM_BYTES = 32  # secrets.token_urlsafe(32) → 43 chars
_SENTINEL = object()  # distinguishes "not passed" from None in update_access


def _hash_token(plaintext: str) -> str:
    """SHA-256 hex digest of the raw token string."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _generate_plaintext() -> str:
    """Generate ``mcp_`` + 43-char random string."""
    return _TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_RANDOM_BYTES)


def _get_or_create_synthetic_user(family_id: int, db: Session) -> User:
    """Return the synthetic ``external_token`` User for *family_id*, creating if needed."""
    user = (
        db.query(User)
        .filter(User.family_id == family_id, User.role == UserRole.EXTERNAL_TOKEN)
        .first()
    )
    if user is not None:
        return user

    user = User(
        id=next_id(),
        family_id=family_id,
        username=f"__mcp_service_{family_id}",
        display_name="MCP Service",
        password_hash="",  # no password — login is rejected by role guard
        role=UserRole.EXTERNAL_TOKEN,
        is_active=True,
    )
    db.add(user)
    return user


def generate_token(family_id: int, db: Session) -> tuple[str, FamilyMCPToken]:
    """Generate a new token for *family_id*, rotating any existing active token.

    Returns ``(plaintext, token_row)``. Plaintext is available **only** from this call.

    Uses SELECT ... FOR UPDATE to prevent concurrent rotation races.
    """
    # Deactivate existing active token (rotation) — use FOR UPDATE to serialize concurrent calls
    existing = (
        db.query(FamilyMCPToken)
        .filter(FamilyMCPToken.family_id == family_id, FamilyMCPToken.is_active.is_(True))
        .with_for_update()
        .first()
    )
    if existing is not None:
        existing.is_active = False
        logger.info("MCP token rotated: family_id=%s", family_id)

    # Ensure synthetic user exists
    _get_or_create_synthetic_user(family_id, db)

    plaintext = _generate_plaintext()
    token_hash = _hash_token(plaintext)

    row = FamilyMCPToken(
        id=next_id(),
        family_id=family_id,
        token_hash=token_hash,
        token_prefix=plaintext[:8],
        token_last4=plaintext[-4:],
        allow_external=False,
        allow_write=False,
        is_active=True,
    )
    db.add(row)
    db.flush()  # populate defaults (server_default timestamps)
    db.refresh(row)

    return plaintext, row


def verify_token(family_id: int, raw_token: str, db: Session) -> FamilyMCPToken | None:
    """Validate *raw_token* for *family_id*.

    Returns the ``FamilyMCPToken`` row on success, ``None`` on any failure.
    Updates ``last_used_at`` on success.
    """
    prefix = raw_token[:8]
    row = (
        db.query(FamilyMCPToken)
        .filter(
            FamilyMCPToken.family_id == family_id,
            FamilyMCPToken.token_prefix == prefix,
            FamilyMCPToken.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        return None

    if not hmac.compare_digest(_hash_token(raw_token), row.token_hash):
        return None

    # Expiration check
    if row.expires_at is not None:
        now = datetime.now(UTC)
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        if now > expires:
            return None

    # Touch last_used_at
    row.last_used_at = datetime.now(UTC)
    db.flush()

    return row


def update_access(
    family_id: int,
    db: Session,
    *,
    allow_external: bool | None = None,
    allow_write: bool | None = None,
    allowed_tools: list[str] | None | object = _SENTINEL,
) -> FamilyMCPToken:
    """PATCH the active token's access flags. Raises 404 if no active token.

    ``expires_at`` is updated directly on the returned row by the caller when
    needed — it lives here (not in the signature) because PATCH needs to
    distinguish "field absent" from "explicit null (never expire)".

    ``allowed_tools``:
    - Not passed (sentinel): no change
    - None: reset to all-available (NULL in DB)
    - list[str]: exact whitelist; validated against registry
    """
    row = (
        db.query(FamilyMCPToken)
        .filter(FamilyMCPToken.family_id == family_id, FamilyMCPToken.is_active.is_(True))
        .first()
    )
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)

    if allow_external is not None:
        row.allow_external = allow_external
    if allow_write is not None:
        row.allow_write = allow_write
    if allowed_tools is not _SENTINEL:
        # Type narrowing: at this point allowed_tools is list[str] | None
        tools_value: list[str] | None = allowed_tools  # type: ignore[assignment]
        if tools_value is not None:
            # Validate against the tool registry
            from apps.backend.app.services.mcp_tool_registry import TOOL_REGISTRY

            invalid = set(tools_value) - set(TOOL_REGISTRY.keys())
            if invalid:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    f"invalid tool names: {sorted(invalid)}",
                )
            row.allowed_tools = json.dumps(tools_value)
        else:
            row.allowed_tools = None

    db.flush()
    db.refresh(row)
    return row


def revoke_token(family_id: int, db: Session) -> None:
    """Soft-deactivate the active token. No-op if none exists."""
    row = (
        db.query(FamilyMCPToken)
        .filter(FamilyMCPToken.family_id == family_id, FamilyMCPToken.is_active.is_(True))
        .first()
    )
    if row is not None:
        row.is_active = False
        db.flush()
        logger.info("MCP token revoked: family_id=%s", family_id)


def get_active_token(family_id: int, db: Session) -> FamilyMCPToken | None:
    """Return the active token row for *family_id*, or None."""
    return (
        db.query(FamilyMCPToken)
        .filter(FamilyMCPToken.family_id == family_id, FamilyMCPToken.is_active.is_(True))
        .first()
    )


def verify_token_by_prefix(raw_token: str, db: Session) -> FamilyMCPToken | None:
    """Validate *raw_token* without family_id (for POST /messages path).

    Returns the ``FamilyMCPToken`` row on success, ``None`` on any failure.
    Does NOT update ``last_used_at`` (caller should do it if needed).

    This function is used by the POST /messages endpoint where family_id is not
    in the URL. The SSE path uses ``verify_token()`` which takes family_id.
    """
    prefix = raw_token[:8]
    row = (
        db.query(FamilyMCPToken)
        .filter(
            FamilyMCPToken.token_prefix == prefix,
            FamilyMCPToken.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        return None

    if not hmac.compare_digest(_hash_token(raw_token), row.token_hash):
        return None

    # Expiration check — critical for POST path which doesn't re-validate at SSE connect
    if row.expires_at is not None:
        now = datetime.now(UTC)
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        if now > expires:
            return None

    if not row.allow_external:
        return None

    return row
