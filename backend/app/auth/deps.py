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
from typing import Optional

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

# OAuth2 for API clients (Bearer token in header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def _verify_token(token: str, expected_type: str = "access") -> Optional[str]:
    """Verify JWT token and return user_id if valid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != expected_type:
            return None
        return user_id
    except JWTError:
        return None


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from either Cookie or Bearer token.

    Priority:
    1. httpOnly Cookie (recommended for web)
    2. Bearer token header (for API clients)

    This dual-mode authentication supports both web browsers (Cookie)
    and API clients like mobile apps or CLI tools (Bearer token).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try Cookie first (recommended for web)
    user_id = None
    if access_token_cookie:
        user_id = _verify_token(access_token_cookie, "access")

    # Fallback to Bearer token (for API clients)
    if user_id is None and token:
        user_id = _verify_token(token, "access")

    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_user_from_cookie(
    access_token_cookie: Optional[str] = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
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
    refresh_token_cookie: Optional[str] = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
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