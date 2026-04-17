"""Authentication dependencies supporting both Cookie and Bearer token authentication.

Security Strategy:
- Primary: httpOnly Cookie (recommended for web apps, XSS-resistant)
- Fallback: Bearer token header (for API clients, mobile apps)

Cookie Configuration:
- httpOnly: JavaScript cannot read (XSS protection)
- secure: HTTPS only (production)
- sameSite: strict (CSRF protection, same-site requests only)
"""

import time
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

# Cookie names
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
CHILD_ACCESS_TOKEN_COOKIE = "child_access_token"
CHILD_REFRESH_TOKEN_COOKIE = "child_refresh_token"

# OAuth2 for API clients (Bearer token in header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ALGORITHM = "HS256"

# JTI revocation store: {jti: expiry_unix_timestamp}
# Entries expire automatically; cleaned up lazily on each revoke call.
_revoked_jtis: dict[str, float] = {}

# Per-user revocation timestamps: {user_id: revoked_before_unix_timestamp}
# Any token with iat <= this value is considered revoked.
_user_revocation_times: dict[str, float] = {}


def revoke_jti(jti: str, ttl_seconds: float) -> None:
    """Mark a single JTI as revoked for ttl_seconds."""
    _revoked_jtis[jti] = time.time() + ttl_seconds
    # Lazy cleanup of already-expired entries
    now = time.time()
    expired = [k for k, exp in list(_revoked_jtis.items()) if exp < now]
    for k in expired:
        del _revoked_jtis[k]


def revoke_all_user_tokens(user_id: str) -> None:
    """Revoke all tokens for a user issued up to this moment."""
    _user_revocation_times[user_id] = time.time()


def _is_jti_revoked(jti: str) -> bool:
    exp = _revoked_jtis.get(jti)
    if exp is None:
        return False
    if time.time() > exp:
        del _revoked_jtis[jti]
        return False
    return True


def _is_token_revoked_for_user(user_id: str, iat: float) -> bool:
    revoked_before = _user_revocation_times.get(user_id)
    if revoked_before is None:
        return False
    return iat <= revoked_before


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid4()), "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create refresh token for adult users.

    Embeds token_version for session revocation support and JTI for single-use rotation.
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    # Embed token_version (defaults to 0 for backward compat)
    token_version = to_encode.get("token_version", 0)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": now,
        "token_version": token_version,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_child_refresh_token(data: dict) -> str:
    """Create long-lived refresh token for child users.

    Child tokens have 10 year expiry for persistent sessions.
    Embeds token_version for session revocation support.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        days=settings.CHILD_REFRESH_TOKEN_EXPIRE_DAYS
    )
    # Embed token_version (defaults to 0 for backward compat)
    token_version = to_encode.get("token_version", 0)
    to_encode.update({"exp": expire, "type": "refresh", "token_version": token_version})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def _verify_token(token: str, expected_type: str = "access") -> str | None:
    """Verify JWT token and return user_id if valid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti: str | None = payload.get("jti")
        iat = payload.get("iat")
        if user_id is None or token_type != expected_type:
            return None
        if jti and _is_jti_revoked(jti):
            return None
        if iat is not None and _is_token_revoked_for_user(user_id, float(iat)):
            return None
        return user_id
    except JWTError:
        return None


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Bearer token or Cookie.

    Priority (SECURITY-CRITICAL):
    1. Bearer token header — used when explicitly provided (API clients)
    2. httpOnly Cookie — fallback for browser sessions without Bearer

    IMPORTANT: Bearer token takes precedence to prevent session hijacking.
    If a client explicitly provides a Bearer token, that identity MUST be used,
    regardless of any cookies the browser may have from other sessions.

    This prevents a critical vulnerability where:
    - UserA sends Bearer token (authenticated as UserA)
    - Browser has UserB's cookie (from prior login)
    - Without this fix: returns UserB (wrong identity, data leak)
    - With this fix: returns UserA (correct identity from Bearer)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = None

    # SECURITY: Bearer token takes precedence over Cookie
    # This prevents session hijacking when API clients send explicit tokens
    if token:
        user_id = _verify_token(token, "access")

    # Fallback to Cookie only when no Bearer token provided
    if user_id is None and access_token_cookie:
        user_id = _verify_token(access_token_cookie, "access")

    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_user_from_cookie(
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Cookie only (strict mode for sensitive operations).

    Use this for endpoints that should only accept Cookie-based auth,
    such as logout or password change operations.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
    )

    if not access_token_cookie:
        raise credentials_exception

    user_id = _verify_token(access_token_cookie, "access")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception

    return user


def get_refresh_token_from_cookie(
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
) -> str:
    """Get refresh token from Cookie for token refresh."""
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
        )

    user_id = _verify_token(refresh_token_cookie, "refresh")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    return refresh_token_cookie


def get_current_child_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
) -> User:
    """Get current child user from child_access_token cookie.

    Similar to get_current_user but reads from child-specific cookie.
    Used by child-authenticated endpoints (verify-parent, logout).

    Returns:
        User object with role='child'

    Raises:
        HTTPException: 401 if not authenticated or not a child user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证儿童凭据",
    )

    # Try Cookie first
    user_id = None
    if child_access_token_cookie:
        user_id = _verify_token(child_access_token_cookie, "access")

    # Fallback to Bearer token
    if user_id is None and token:
        user_id = _verify_token(token, "access")

    if user_id is None:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.is_active == True,
            User.role == "child",
        )
        .first()
    )
    if user is None:
        raise credentials_exception

    return user


def get_child_refresh_token_from_cookie(
    child_refresh_token_cookie: str | None = Cookie(
        None, alias=CHILD_REFRESH_TOKEN_COOKIE
    ),
) -> str:
    """Get child refresh token from Cookie for token refresh."""
    if not child_refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少儿童刷新令牌",
        )

    user_id = _verify_token(child_refresh_token_cookie, "refresh")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的儿童刷新令牌",
        )

    return child_refresh_token_cookie


def require_adult(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an adult (owner or member).

    Raises HTTP 403 if the user has role='child'.
    Apply per-function by replacing get_current_user with require_adult.
    """
    if user.role == "child":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="子账户无权访问此功能",
        )
    return user