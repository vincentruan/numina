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
from uuid import uuid4

import bcrypt
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.deps import create_access_token, create_refresh_token
from app.models.family import Family, generate_invite_code
from app.models.user import User
from app.schemas.auth import (
    JoinFamilyRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)
from app.services.security_log import _log_security_event, SecurityEventType

# Login rate limiting: {username: (fail_count, first_fail_time)}
_login_attempts: dict[str, tuple[int, float]] = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60  # 15 minutes

# Dummy hash cache for timing attack protection
_dummy_hash_cache: str | None = None


def _get_rate_limit_settings():
    """Get rate limit settings from config."""
    try:
        from app.config import settings
        return settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS
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
        _dummy_hash_cache = bcrypt.hashpw(b"dummy_password", bcrypt.gensalt(rounds=rounds)).decode("utf-8")
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
            _log_security_event(SecurityEventType.REGISTER_RATE_LIMITED, client_ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"注册请求过于频繁，请 {remaining_minutes} 分钟后重试",
            )
    except HTTPException:
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
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录失败次数过多，请 {remaining} 分钟后重试",
            )
    except Exception:
        # Fallback to in-memory if cache not available
        if username not in _login_attempts:
            return
        count, first_time = _login_attempts[username]
        if count >= max_attempts:
            elapsed = time.time() - first_time
            if elapsed < lockout_seconds:
                remaining = int((lockout_seconds - elapsed) / 60) + 1
                _log_security_event(SecurityEventType.LOGIN_RATE_LIMITED, username=username)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"登录失败次数过多，请 {remaining} 分钟后重试",
                )
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
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def register(db: Session, req: RegisterRequest, client_ip: str = "unknown") -> TokenResponse:
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

    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    family_id = str(uuid4())
    user_id = str(uuid4())

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

    # Record successful registration for rate limiting
    _record_register_attempt(client_ip)
    _log_security_event(SecurityEventType.REGISTER_SUCCESS, username=req.username, user_id=user_id)

    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def login(db: Session, req: LoginRequest) -> TokenResponse:
    _check_rate_limit(req.username)

    user = db.query(User).filter(User.username == req.username, User.is_active == True).first()
    # Timing attack protection: always execute bcrypt to ensure consistent response time
    if user is None:
        # User not found - verify against dummy hash to consume similar time
        dummy_hash = _get_dummy_hash()
        bcrypt.checkpw(req.password.encode("utf-8"), dummy_hash.encode("utf-8"))
        _record_failed_login(req.username)
        _log_security_event(SecurityEventType.LOGIN_FAILED_USER_NOT_FOUND, username=req.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    # User found - normal verification
    if not verify_password(req.password, user.password_hash):
        _record_failed_login(req.username)
        _log_security_event(SecurityEventType.LOGIN_FAILED_WRONG_PASSWORD, username=req.username, user_id=user.id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    _clear_failed_login(req.username)
    _log_security_event(SecurityEventType.LOGIN_SUCCESS, username=req.username, user_id=user.id)
    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def refresh_token(db: Session, refresh_tok: str) -> TokenResponse:
    from jose import JWTError, jwt
    from app.config import settings
    from app.auth.deps import ALGORITHM

    try:
        payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def join_family(db: Session, req: JoinFamilyRequest) -> TokenResponse:
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    family = db.query(Family).filter(Family.invite_code == req.invite_code).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请码无效")

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
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def update_profile(db: Session, user: User, req: UpdateProfileRequest) -> User:
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.avatar_color is not None:
        user.avatar_color = req.avatar_color
    db.commit()
    db.refresh(user)
    return user
