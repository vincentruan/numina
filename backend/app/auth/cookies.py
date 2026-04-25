"""Cookie-based authentication helpers.

Cookie Security Configuration:
- httpOnly: True - JavaScript cannot read (XSS protection)
- secure: True in production - HTTPS only
- sameSite: 'strict' - Same-site requests only (CSRF protection)
- path: '/' - Available for all routes

Trade-offs:
- sameSite='strict': Most secure, but breaks cross-site navigation
  (e.g., clicking a link from email won't carry auth cookie)
- Alternative: sameSite='lax' allows cross-site GET but blocks POST
  For this app, 'strict' is appropriate (no cross-site auth needed)

References:
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
- https://owasp.org/www-community/attacks/csrf
"""

from fastapi import Response

from app.auth.deps import (
    ACCESS_TOKEN_COOKIE,
    CHILD_ACCESS_TOKEN_COOKIE,
    CHILD_REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
)
from app.config import settings


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set authentication cookies on response.

    Args:
        response: FastAPI response object
        access_token: JWT access token (15 min expiry)
        refresh_token: JWT refresh token (7 day expiry)
    """
    # Access token cookie (short-lived)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 15 min = 900s
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )

    # Refresh token cookie (long-lived)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 7 days = 604800s
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies on logout.

    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path="/",
    )
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path="/",
    )


def set_child_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set child authentication cookies on response.

    Args:
        response: FastAPI response object
        access_token: JWT access token (15 min expiry, same as adult)
        refresh_token: JWT refresh token (30 day expiry)
    """
    # Child access token cookie (same short-lived as adult)
    response.set_cookie(
        key=CHILD_ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 15 min = 900s
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )

    # Child refresh token cookie (30 days, same as trusted adult sessions)
    response.set_cookie(
        key=CHILD_REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.CHILD_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )


def clear_child_auth_cookies(response: Response) -> None:
    """Clear child authentication cookies on logout.

    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key=CHILD_ACCESS_TOKEN_COOKIE,
        path="/",
    )
    response.delete_cookie(
        key=CHILD_REFRESH_TOKEN_COOKIE,
        path="/",
    )
