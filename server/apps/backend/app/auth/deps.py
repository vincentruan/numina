"""Authentication dependencies supporting both Cookie and Bearer token authentication.

Security Strategy:
- Primary: httpOnly Cookie (recommended for web apps, XSS-resistant)
- Fallback: Bearer token header (for API clients, mobile apps)

Cookie Configuration:
- httpOnly: JavaScript cannot read (XSS protection)
- secure: HTTPS only (production)
- sameSite: strict (CSRF protection, same-site requests only)
"""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from apps.backend.app.auth.revoke_jti import (
    _is_jti_revoked,
    _is_token_revoked_for_user,
)
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User

# Cookie names
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
CHILD_ACCESS_TOKEN_COOKIE = "child_access_token"
CHILD_REFRESH_TOKEN_COOKIE = "child_refresh_token"

# OAuth2 for API clients (Bearer token in header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ALGORITHM = "HS256"



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


def _verify_token(token: str, expected_type: str = "access") -> dict | None:
    """Verify JWT token and return payload dict if valid.

    Returns dict with keys:
    - sub: user_id (always present)
    - fid: family_id (None for child tokens, present for adult tokens)
    - role: user role (defaults to "member" for backward compat with adult tokens)

    SECURITY: All existing revocation checks preserved:
    - JTI revocation check
    - iat-based per-user revocation check
    - token type validation
    """
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
        # Extract fid and role with defaults for backward compat
        fid: str | None = payload.get("fid")  # Present for all tokens after refactor
        role: str = payload.get("role", "member")  # Default for backward compat with old tokens
        return {"sub": user_id, "fid": fid, "role": role}
    except JWTError:
        return None


def _assert_not_child(user: User) -> None:
    """Raise 403 if the user is a child account.

    Called from get_current_user and get_current_user_from_cookie to block
    child tokens on all adult endpoints at the authentication layer.
    """
    if user.role == "child":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="儿童账户无法访问此端点",
        )


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

    Performance: Uses embedded fid/role from JWT payload, minimal DB check.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = None

    # SECURITY: Bearer token takes precedence over Cookie
    # This prevents session hijacking when API clients send explicit tokens
    if token:
        payload = _verify_token(token, "access")

    # Fallback to Cookie only when no Bearer token provided
    if payload is None and access_token_cookie:
        payload = _verify_token(access_token_cookie, "access")

    if payload is None:
        raise credentials_exception

    user_id = payload["sub"]
    payload_fid = payload["fid"]
    payload_role = payload["role"]

    # SECURITY: Minimal existence check + family_id verification
    # Prevents cross-family data access after user removal from family
    # Query returns columns needed by UserResponse schema, not full User object
    result = db.query(
        User.family_id,
        User.username,
        User.display_name,
        User.avatar_color,
        User.theme,
        User.language,
        User.default_currency,
        User.view_mode,
    ).filter(
        User.id == int(user_id), User.is_active.is_(True)
    ).first()

    if result is None:
        # User doesn't exist or is inactive
        raise credentials_exception

    (
        db_family_id,
        username,
        display_name,
        avatar_color,
        theme,
        language,
        default_currency,
        view_mode,
    ) = result

    # SECURITY: Verify payload fid matches current DB family_id
    # This prevents stale tokens from accessing data after family removal
    if int(payload_fid) != db_family_id:
        raise credentials_exception

    # SECURITY: child tokens must not be accepted on adult endpoints.
    # Endpoints that need child access use get_current_child_user instead.
    if payload_role == "child":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="儿童账户无法访问此端点",
        )

    # Return User object with queried columns + payload fields
    # Saves ~7 columns compared to full User query (no password_hash, pin fields, etc.)
    user = User(
        id=int(user_id),
        family_id=int(payload_fid),
        username=username,
        display_name=display_name,
        avatar_color=avatar_color,
        role=payload_role,
        is_active=True,
        theme=theme,
        language=language,
        default_currency=default_currency,
        view_mode=view_mode,
    )
    # Merge into session so services can use db.refresh() for write operations
    merged_user = db.merge(user)
    return merged_user


def get_current_user_from_cookie(
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Cookie only (strict mode for sensitive operations).

    Use this for endpoints that should only accept Cookie-based auth,
    such as logout or password change operations.

    Performance: Uses embedded fid/role from JWT payload, minimal DB check.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
    )

    if not access_token_cookie:
        raise credentials_exception

    payload = _verify_token(access_token_cookie, "access")
    if payload is None:
        raise credentials_exception

    user_id = payload["sub"]
    payload_fid = payload["fid"]
    payload_role = payload["role"]

    # SECURITY: Minimal existence check + family_id verification
    # Query returns columns needed by UserResponse schema
    result = db.query(
        User.family_id,
        User.username,
        User.display_name,
        User.avatar_color,
        User.theme,
        User.language,
        User.default_currency,
        User.view_mode,
    ).filter(
        User.id == int(user_id), User.is_active.is_(True)
    ).first()

    if result is None:
        raise credentials_exception

    (
        db_family_id,
        username,
        display_name,
        avatar_color,
        theme,
        language,
        default_currency,
        view_mode,
    ) = result

    # SECURITY: Verify payload fid matches current DB family_id
    if int(payload_fid) != db_family_id:
        raise credentials_exception

    # SECURITY: child tokens must not be accepted on adult-only cookie endpoints.
    if payload_role == "child":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="儿童账户无法访问此端点",
        )

    # Return User object with queried columns + payload fields
    user = User(
        id=int(user_id),
        family_id=int(payload_fid),
        username=username,
        display_name=display_name,
        avatar_color=avatar_color,
        role=payload_role,
        is_active=True,
        theme=theme,
        language=language,
        default_currency=default_currency,
        view_mode=view_mode,
    )
    # Merge into session so services can use db.refresh() for write operations
    merged_user = db.merge(user)
    return merged_user


def get_refresh_token_from_cookie(
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
) -> str:
    """Get refresh token from Cookie for token refresh."""
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
        )

    payload = _verify_token(refresh_token_cookie, "refresh")
    if payload is None:
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
    """Get current child user from Bearer token or Cookie.

    Priority (SECURITY-CRITICAL):
    1. Bearer token header — used when explicitly provided (API clients)
    2. httpOnly Cookie — fallback for browser sessions without Bearer

    IMPORTANT: Bearer token takes precedence to prevent session hijacking.
    If a client explicitly provides a Bearer token, that identity MUST be used,
    regardless of any cookies the browser may have from other sessions.

    Returns:
        User object with role='child'

    Raises:
        HTTPException: 401 if not authenticated or not a child user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证儿童凭据",
    )

    payload = None

    # SECURITY: Bearer token takes precedence over Cookie
    if token:
        payload = _verify_token(token, "access")

    # Fallback to Cookie only when no Bearer token provided
    if payload is None and child_access_token_cookie:
        payload = _verify_token(child_access_token_cookie, "access")

    if payload is None:
        raise credentials_exception

    user_id = payload["sub"]
    payload_fid = payload["fid"]
    payload_role = payload["role"]

    # SECURITY: Verify payload role is child
    if payload_role != "child":
        raise credentials_exception

    # SECURITY: Minimal existence check + role verification + family_id verification
    # Query returns columns needed for child user operations
    result = db.query(
        User.family_id,
        User.username,
        User.display_name,
        User.avatar_color,
        User.theme,
        User.language,
        User.default_currency,
        User.view_mode,
    ).filter(
        User.id == int(user_id),
        User.is_active.is_(True),
        User.role == "child",
    ).first()

    if result is None:
        raise credentials_exception

    (
        db_family_id,
        username,
        display_name,
        avatar_color,
        theme,
        language,
        default_currency,
        view_mode,
    ) = result

    # SECURITY: Verify payload fid matches current DB family_id
    if int(payload_fid) != db_family_id:
        raise credentials_exception

    # Return User object with queried columns + payload fields
    user = User(
        id=int(user_id),
        family_id=int(payload_fid),
        username=username,
        display_name=display_name,
        avatar_color=avatar_color,
        role="child",
        is_active=True,
        theme=theme,
        language=language,
        default_currency=default_currency,
        view_mode=view_mode,
    )
    # Merge into session so services can use db.refresh() for write operations
    merged_user = db.merge(user)
    return merged_user


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

    payload = _verify_token(child_refresh_token_cookie, "refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的儿童刷新令牌",
        )

    return child_refresh_token_cookie


def get_current_user_or_child(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Bearer token or Cookie (adult OR child).

    This is used for endpoints like /auth/me that should work for both adults and children.
    Priority: Bearer token → adult cookie → child cookie.

    SECURITY: Bearer token takes precedence to prevent session hijacking.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
    )

    payload = None

    # SECURITY: Bearer token takes precedence
    if token:
        payload = _verify_token(token, "access")

    # Fallback: try adult cookie first, then child cookie
    if payload is None and access_token_cookie:
        payload = _verify_token(access_token_cookie, "access")

    if payload is None and child_access_token_cookie:
        payload = _verify_token(child_access_token_cookie, "access")

    if payload is None:
        raise credentials_exception

    user_id = payload["sub"]
    payload_fid = payload["fid"]
    payload_role = payload["role"]

    # Minimal existence check + family_id verification
    result = db.query(
        User.family_id,
        User.username,
        User.display_name,
        User.avatar_color,
        User.theme,
        User.language,
        User.default_currency,
        User.view_mode,
    ).filter(
        User.id == int(user_id), User.is_active.is_(True)
    ).first()

    if result is None:
        raise credentials_exception

    (
        db_family_id,
        username,
        display_name,
        avatar_color,
        theme,
        language,
        default_currency,
        view_mode,
    ) = result

    # SECURITY: Verify payload fid matches current DB family_id
    if int(payload_fid) != db_family_id:
        raise credentials_exception

    # Return User object (role can be adult or child)
    user = User(
        id=int(user_id),
        family_id=int(payload_fid),
        username=username,
        display_name=display_name,
        avatar_color=avatar_color,
        role=payload_role,
        is_active=True,
        theme=theme,
        language=language,
        default_currency=default_currency,
        view_mode=view_mode,
    )
    merged_user = db.merge(user)
    return merged_user


def require_adult(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an adult (owner or member).

    Child tokens are already rejected by get_current_user via _assert_not_child.
    This explicit check is defense-in-depth: if get_current_user ever changes,
    require_adult still enforces the invariant independently.
    """
    _assert_not_child(user)
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be the family owner.

    Raises AppError AUTH_OWNER_ONLY if the user is not role='owner'.
    Use for operations that only the family owner should perform,
    such as approving chores or managing family settings.
    """
    from apps.backend.app.errors import AppError, ErrorCode

    if user.role != "owner":
        raise AppError(ErrorCode.AUTH_OWNER_ONLY)
    return user


# ---------------------------------------------------------------------------
# Temporary token for two-step login
# ---------------------------------------------------------------------------

_TEMP_TOKEN_EXPIRE_MINUTES = 15  # Extended for child emoji PIN selection


def create_temp_token(user_id: int, role: str) -> str:
    """Create a short-lived token for the second step of two-step login."""
    to_encode = {
        "sub": str(user_id),
        "role": role,
        "type": "temp",
        "exp": datetime.utcnow() + timedelta(minutes=_TEMP_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_temp_token(temp_token: str) -> dict:
    """Verify a temporary login token and return its payload.

    Raises HTTPException 401 if invalid or expired.
    """
    try:
        payload = jwt.decode(temp_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "temp":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的临时令牌")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="临时令牌已过期或无效")
