"""Authentication service with security enhancements.

Security Features:
- Timing attack protection: Dummy bcrypt verification for non-existent users
- Configurable bcrypt rounds via BCRYPT_ROUNDS setting
- Login rate limiting by username (5 attempts, 15 min lockout)
- Registration rate limiting by IP (5 attempts per hour)

Rate Limiting Trade-offs:
- Username-based rate limiting prevents brute-force attacks on specific accounts
- Limitation: Attackers can try different usernames to bypass the limit
- Mitigation: Global API rate limiting (by IP) provides a second defense layer
- Registration rate limiting prevents bulk account creation

See design.md for detailed trade-off analysis.
"""

import time
from datetime import datetime, timedelta

import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session

from app.auth.deps import create_access_token, create_refresh_token
from app.auth.jwt_utils import user_claims
from app.errors import AppError, ErrorCode
from app.models.family import Family
from app.models.family_invitation_code import FamilyInvitationCode
from app.models.user import User
from app.schemas.auth import (
    JoinFamilyRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)
from app.services.audit_log import write_audit_log
from app.services.device import rotate_device_session_jti
from app.services.security_log import SecurityEventType, _log_security_event

# Login rate limiting: {username: (fail_count, first_fail_time)}
_login_attempts: dict[str, tuple[int, float]] = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60  # 15 minutes

# Dummy hash cache for timing attack protection
_dummy_hash_cache: str | None = None

# Refresh rate limit: 10 per minute per user_id
_REFRESH_RATE_LIMIT_PER_MINUTE = 10
# Password change rate limit: 3 per hour per user_id
_PASSWORD_CHANGE_RATE_LIMIT_PER_HOUR = 3


def _check_refresh_rate_limit(user_id: str) -> None:
    """Limit token refresh to 10 per minute per user."""
    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"refresh_attempts:{user_id}"
        count = cache.get(key)
        if count is not None and int(count) >= _REFRESH_RATE_LIMIT_PER_MINUTE:
            _log_security_event(
                SecurityEventType.TOKEN_REFRESH_FAILED,
                user_id=user_id,
                reason="rate_limited",
            )
            raise AppError(ErrorCode.AUTH_RATE_LIMITED)
        new_count = cache.increment(key)
        if new_count == 1:
            cache.set(key, 1, ttl_seconds=60)
    except AppError:
        raise
    except Exception:
        pass


def _check_password_change_rate_limit(user_id: str) -> None:
    """Limit password changes to 3 per hour per user."""
    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"password_change_attempts:{user_id}"
        count = cache.get(key)
        if count is not None and int(count) >= _PASSWORD_CHANGE_RATE_LIMIT_PER_HOUR:
            _log_security_event(
                SecurityEventType.PASSWORD_CHANGE_FAILED,
                user_id=user_id,
                reason="rate_limited",
            )
            raise AppError(ErrorCode.AUTH_RATE_LIMITED)
        new_count = cache.increment(key)
        if new_count == 1:
            cache.set(key, 1, ttl_seconds=3600)
    except AppError:
        raise
    except Exception:
        pass


def _get_rate_limit_settings():
    """Get rate limit settings from config."""
    try:
        from app.config import settings

        return (
            settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
            settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS,
        )
    except (ImportError, AttributeError):
        return _MAX_ATTEMPTS, _LOCKOUT_SECONDS


def _get_register_rate_limit_settings():
    """Get registration rate limit settings from config."""
    try:
        from app.config import settings

        return settings.REGISTER_RATE_LIMIT_PER_HOUR
    except (ImportError, AttributeError):
        return 5  # Default: 5 per hour


def _get_dummy_hash() -> str:
    """Get or create a dummy hash for timing attack protection."""
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        # Use configured rounds from settings
        try:
            from app.config import settings

            rounds = settings.BCRYPT_ROUNDS
        except (ImportError, AttributeError):
            rounds = 12  # Default fallback
        _dummy_hash_cache = bcrypt.hashpw(
            b"dummy_password", bcrypt.gensalt(rounds=rounds)
        ).decode("utf-8")
    return _dummy_hash_cache


def _get_client_ip(request: Request) -> str:
    """Get real client IP from request with trusted proxy validation."""
    from app.middleware.rate_limit import _get_real_client_ip

    return _get_real_client_ip(request)


def _check_register_rate_limit(client_ip: str) -> None:
    """Check if IP is rate limited for registration.

    Limits registration to REGISTER_RATE_LIMIT_PER_HOUR per IP per hour.
    """
    max_per_hour = _get_register_rate_limit_settings()

    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"register_attempts:{client_ip}"
        count = cache.get(key)
        if count is not None and int(count) >= max_per_hour:
            ttl = cache.get_ttl(key) or 0
            remaining_minutes = max(1, ttl // 60)
            _log_security_event(
                SecurityEventType.REGISTER_RATE_LIMITED, client_ip=client_ip
            )
            raise AppError(ErrorCode.AUTH_RATE_LIMITED)
    except AppError:
        raise
    except Exception:
        # If cache not available, allow registration (fail open)
        pass


def _record_register_attempt(client_ip: str) -> None:
    """Record a registration attempt for rate limiting."""
    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"register_attempts:{client_ip}"
        count = cache.increment(key)
        # Set TTL on first attempt (1 hour = 3600 seconds)
        if count == 1:
            cache.set(key, 1, ttl_seconds=3600)
    except Exception:
        # If cache not available, skip tracking
        pass


def _check_rate_limit(username: str) -> None:
    """Check if user is rate limited due to too many failed login attempts."""
    max_attempts, lockout_seconds = _get_rate_limit_settings()

    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"login_attempts:{username}"
        count = cache.get(key)
        if count is not None and int(count) >= max_attempts:
            ttl = cache.get_ttl(key) or 0
            remaining = max(1, (ttl // 60) + 1)
            _log_security_event(SecurityEventType.LOGIN_RATE_LIMITED, username=username)
            raise AppError(ErrorCode.AUTH_RATE_LIMITED)
    except Exception:
        # Fallback to in-memory if cache not available
        if username not in _login_attempts:
            return
        count, first_time = _login_attempts[username]
        if count >= max_attempts:
            elapsed = time.time() - first_time
            if elapsed < lockout_seconds:
                remaining = int((lockout_seconds - elapsed) / 60) + 1
                _log_security_event(
                    SecurityEventType.LOGIN_RATE_LIMITED, username=username
                )
                raise AppError(ErrorCode.AUTH_RATE_LIMITED)
            del _login_attempts[username]


def _record_failed_login(username: str) -> None:
    """Record a failed login attempt."""
    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"login_attempts:{username}"
        cache.increment(key)
        # Set TTL on first attempt
        _, lockout_seconds = _get_rate_limit_settings()
        if cache.get(key) == 1:
            cache.set(key, 1, ttl_seconds=lockout_seconds)
    except Exception:
        # Fallback to in-memory
        if username in _login_attempts:
            count, first_time = _login_attempts[username]
            _login_attempts[username] = (count + 1, first_time)
        else:
            _login_attempts[username] = (1, time.time())


def _clear_failed_login(username: str) -> None:
    """Clear failed login attempts for a user."""
    try:
        from app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"login_attempts:{username}"
        cache.delete(key)
    except Exception:
        _login_attempts.pop(username, None)


def hash_password(password: str) -> str:
    """Hash password with bcrypt. Uses configured rounds from settings."""
    try:
        from app.config import settings

        rounds = settings.BCRYPT_ROUNDS
    except (ImportError, AttributeError):
        rounds = 12  # Default fallback
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def register(
    db: Session, req: RegisterRequest, client_ip: str = "unknown"
) -> TokenResponse:
    """Register a new user with rate limiting.

    Args:
        db: Database session
        req: Registration request
        client_ip: Client IP for rate limiting

    Returns:
        TokenResponse with access and refresh tokens
    """
    # Check registration rate limit
    _check_register_rate_limit(client_ip)

    # Validate family invitation code
    invitation_code = (
        db.query(FamilyInvitationCode)
        .filter(FamilyInvitationCode.code == req.family_invitation_code)
        .first()
    )
    if not invitation_code:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_NOT_FOUND)
    if invitation_code.is_used:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_ALREADY_USED)
    if invitation_code.revoked_at is not None:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_REVOKED)

    if db.query(User).filter(User.username == req.username).first():
        raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)

    # Generate snowflake IDs explicitly so we can cross-reference family/user
    from app.utils.snowflake import next_id as _next_id
    family_id = _next_id()
    user_id = _next_id()

    family = Family(
        id=family_id,
        name=req.family_name,
        created_by=user_id,
    )
    db.add(family)

    user = User(
        id=user_id,
        family_id=family_id,
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="owner",
    )
    db.add(user)
    db.commit()

    # Mark invitation code as used after successful registration
    invitation_code.is_used = True
    invitation_code.used_at = datetime.utcnow()
    invitation_code.used_by_family_id = family_id
    invitation_code.used_by_username = req.username
    db.commit()

    # Record successful registration for rate limiting
    _record_register_attempt(client_ip)
    _log_security_event(
        SecurityEventType.REGISTER_SUCCESS, username=req.username, user_id=user_id
    )

    return TokenResponse(
        access_token=create_access_token(
            user_claims(user)
        ),
        refresh_token=create_refresh_token(
            user_claims(user)
        ),
    )


def login(db: Session, req: LoginRequest) -> TokenResponse:
    _check_rate_limit(req.username)

    user = (
        db.query(User)
        .filter(User.username == req.username, User.is_active == True)
        .first()
    )
    # Timing attack protection: always execute bcrypt to ensure consistent response time
    if user is None:
        # User not found - verify against dummy hash to consume similar time
        dummy_hash = _get_dummy_hash()
        bcrypt.checkpw(req.password.encode("utf-8"), dummy_hash.encode("utf-8"))
        _record_failed_login(req.username)
        _log_security_event(
            SecurityEventType.LOGIN_FAILED_USER_NOT_FOUND, username=req.username
        )
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # User found - normal verification
    if not verify_password(req.password, user.password_hash):
        _record_failed_login(req.username)
        _log_security_event(
            SecurityEventType.LOGIN_FAILED_WRONG_PASSWORD,
            username=req.username,
            user_id=user.id,
        )
        write_audit_log(
            "login_failed",
            "failure",
            user_id=user.id,
            family_id=user.family_id,
            detail="wrong_password",
        )
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    _clear_failed_login(req.username)
    _log_security_event(
        SecurityEventType.LOGIN_SUCCESS, username=req.username, user_id=user.id
    )
    write_audit_log(
        "login_success", "success", user_id=user.id, family_id=user.family_id
    )
    return TokenResponse(
        access_token=create_access_token(
            user_claims(user)
        ),
        refresh_token=create_refresh_token(
            user_claims(user)
        ),
    )


def refresh_token(db: Session, refresh_tok: str) -> TokenResponse:
    from jose import JWTError, jwt

    from app.auth.deps import ALGORITHM, _verify_token
    from app.auth.revoke_jti import revoke_jti
    from app.config import settings

    # Use _verify_token so JTI revocation check is applied
    payload = _verify_token(refresh_tok, "refresh")
    if payload is None:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    user_id = payload["sub"]

    try:
        payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=[ALGORITHM])
        old_jti = payload.get("jti")
    except JWTError:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    # Validate token_version to support force-logout
    claim_version = payload.get("token_version", 0)
    if claim_version != user.token_version:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    # Rate limit refresh attempts per user
    _check_refresh_rate_limit(user_id)

    # Revoke the old refresh token JTI so it can't be reused
    new_refresh_token = create_refresh_token(user_claims(user, token_version=user.token_version))
    if old_jti:
        revoke_jti(old_jti, ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
        new_payload = jwt.decode(new_refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        new_jti = new_payload.get("jti")
        if new_jti:
            rotate_device_session_jti(db, old_jti=old_jti, new_jti=new_jti)

    _log_security_event(SecurityEventType.TOKEN_REFRESH_SUCCESS, user_id=user_id)
    write_audit_log(
        "token_refresh", "success", user_id=user.id, family_id=user.family_id
    )
    return TokenResponse(
        access_token=create_access_token(user_claims(user)),
        refresh_token=new_refresh_token,
    )


def join_family(db: Session, req: JoinFamilyRequest) -> TokenResponse:
    if db.query(User).filter(User.username == req.username).first():
        raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)

    family = db.query(Family).filter(Family.invite_code == req.invite_code).first()
    if not family:
        raise AppError(ErrorCode.AUTH_INVITE_CODE_INVALID)

    user = User(
        family_id=family.id,
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(
            user_claims(user)
        ),
        refresh_token=create_refresh_token(
            user_claims(user)
        ),
    )


def change_password(
    db: Session, user: User, old_password: str, new_password: str
) -> None:
    """Change user password and revoke all existing tokens."""
    from app.auth.revoke_jti import revoke_all_user_tokens

    _check_password_change_rate_limit(user.id)

    if not verify_password(old_password, user.password_hash):
        _log_security_event(SecurityEventType.PASSWORD_CHANGE_FAILED, user_id=user.id)
        raise AppError(ErrorCode.AUTH_PASSWORD_INCORRECT)

    user.password_hash = hash_password(new_password)
    db.commit()

    # Revoke all tokens issued before now
    revoke_all_user_tokens(user.id)
    _log_security_event(SecurityEventType.PASSWORD_CHANGE_SUCCESS, user_id=user.id)
    write_audit_log(
        "password_change", "success", user_id=user.id, family_id=user.family_id
    )


def update_profile(db: Session, user: User, req: UpdateProfileRequest) -> User:
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.avatar_color is not None:
        user.avatar_color = req.avatar_color
    db.commit()
    db.refresh(user)
    return user


def verify_parent_password(db: Session, child_user: User, password: str) -> None:
    """Verify that the given password matches any parent (owner/member) in the child's family.

    Used to gate adult-only actions on shared devices while in child mode.
    Always runs bcrypt to prevent timing-based family membership enumeration.

    Raises:
        AppError(AUTH_INVALID_CREDENTIALS): if no parent password matches
    """
    parents = (
        db.query(User)
        .filter(
            User.family_id == child_user.family_id,
            User.role.in_(["owner", "member"]),
            User.is_active == True,
            User.password_hash.isnot(None),
        )
        .all()
    )

    # Always run at least one bcrypt verify for timing consistency
    if not parents:
        bcrypt.checkpw(password.encode("utf-8"), _get_dummy_hash().encode("utf-8"))
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    for parent in parents:
        if verify_password(password, parent.password_hash):
            return

    raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)


# ---------------------------------------------------------------------------
# Child PIN auth
# ---------------------------------------------------------------------------

_CHILD_PIN_MAX_ATTEMPTS = 3
_CHILD_PIN_LOCKOUT_MINUTES = 15


def child_pin_login(
    db: Session, child_id: str | None, username: str | None, pin_sequence: list[str]
) -> TokenResponse:
    """Verify child PIN and return tokens. Enforces lockout after 3 failures.

    支持双模式登录：
    - username + PIN（主要方式）
    - child_id + PIN（备选方式，向后兼容）
    """
    import unicodedata

    from app.auth.deps import create_access_token, create_child_refresh_token

    # 根据 identifier 类型查找儿童
    if username:
        child = (
            db.query(User)
            .filter(
                User.username == username.lower(),
                User.is_active == True,
                User.role == "child",
            )
            .first()
        )
    else:
        child = (
            db.query(User)
            .filter(User.id == child_id, User.is_active == True, User.role == "child")
            .first()
        )

    # Timing attack protection: always run bcrypt even if child not found
    if not child or child.pin_hash is None:
        bcrypt.checkpw(b"dummy", _get_dummy_hash().encode("utf-8"))
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # Check lockout (after dummy bcrypt to avoid timing leak on locked state)
    if (
        child.pin_locked_until is not None
        and child.pin_locked_until > datetime.utcnow()
    ):
        bcrypt.checkpw(b"dummy", _get_dummy_hash().encode("utf-8"))
        raise AppError(
            ErrorCode.AUTH_PIN_LOCKED,
            details={"locked_until": child.pin_locked_until.isoformat()},
        )

    # Verify PIN using bcrypt.checkpw
    normalized = unicodedata.normalize("NFC", "".join(pin_sequence))
    if not bcrypt.checkpw(normalized.encode("utf-8"), child.pin_hash.encode("utf-8")):
        _record_child_pin_failure(db, child)
        _log_security_event(
            SecurityEventType.LOGIN_FAILED_WRONG_PASSWORD, user_id=child.id
        )
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # Success — clear lockout state and reset fail counter
    child.pin_locked_until = None
    child.pin_fail_count = 0
    _child_pin_attempts.pop(child.id, None)
    db.commit()

    _log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id=child.id)
    return TokenResponse(
        access_token=create_access_token(user_claims(child)),
        refresh_token=create_child_refresh_token(user_claims(child, token_version=child.token_version)),
    )


def admin_switch_to_child(db: Session, owner: User, child_id: str) -> TokenResponse:
    """Admin switches to child view without PIN verification.

    Args:
        db: Database session
        owner: Current owner user (must have role='owner')
        child_id: Target child ID to switch to

    Returns:
        TokenResponse with child access and refresh tokens

    Raises:
        AppError: If child not found or not in same family
    """
    from app.auth.deps import create_access_token, create_child_refresh_token

    # Verify child exists and belongs to owner's family
    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == owner.family_id,
            User.role == "child",
            User.is_active == True,
        )
        .first()
    )

    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    # Generate child tokens (same as child_pin_login)
    return TokenResponse(
        access_token=create_access_token(user_claims(child)),
        refresh_token=create_child_refresh_token(user_claims(child, token_version=child.token_version)),
    )


# Child PIN failure tracking: {child_id: (fail_count, first_fail_time)}
_child_pin_attempts: dict[str, tuple[int, float]] = {}


def _record_child_pin_failure(db: Session, child: User) -> None:
    child_id = child.id
    now = time.time()
    count, first_time = _child_pin_attempts.get(child_id, (0, now))

    # Reset window if first failure was > lockout period ago
    if now - first_time > _CHILD_PIN_LOCKOUT_MINUTES * 60:
        count, first_time = 0, now

    count += 1
    _child_pin_attempts[child_id] = (count, first_time)

    # Update DB pin_fail_count
    child.pin_fail_count = count
    db.commit()

    if count >= _CHILD_PIN_MAX_ATTEMPTS:
        child.pin_locked_until = datetime.utcnow() + timedelta(
            minutes=_CHILD_PIN_LOCKOUT_MINUTES
        )
        db.commit()
        del _child_pin_attempts[child_id]


def child_refresh_token(db: Session, refresh_tok: str) -> TokenResponse:
    """Refresh child access token using child refresh token."""
    from jose import JWTError, jwt

    from app.auth.deps import ALGORITHM, create_access_token
    from app.config import settings

    try:
        payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type != "refresh":
            raise AppError(ErrorCode.AUTH_REFRESH_FAILED)
    except JWTError:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    child = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not child or child.pin_hash is None:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    # Validate token_version to support force-logout
    claim_version = payload.get("token_version", 0)
    if claim_version != child.token_version:
        raise AppError(ErrorCode.AUTH_REFRESH_FAILED)

    return TokenResponse(
        access_token=create_access_token(
            user_claims(child)
        ),
        refresh_token=refresh_tok,  # keep same refresh token
    )
