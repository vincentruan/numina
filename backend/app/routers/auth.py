"""Authentication endpoints with Cookie-based auth support.

Dual-mode authentication:
- Cookie mode: Recommended for web browsers (XSS-resistant)
- Bearer mode: For API clients (mobile apps, CLI tools)

Cookie is set automatically on login/register, Bearer token still returned
in response body for backward compatibility.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.captcha import verify_captcha
from app.auth.cookies import set_auth_cookies, clear_auth_cookies
from app.auth.deps import (
    get_current_user,
    get_current_user_from_cookie,
    get_refresh_token_from_cookie,
)
from app.database import get_db
from app.middleware.rate_limit import _get_real_client_ip
from app.models.user import User
from app.schemas.auth import (
    JoinFamilyRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UpdateSettingsRequest,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(
    response: Response,
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    """Register a new user and set authentication cookies.

    Returns tokens in both Cookie (httpOnly) and JSON body (for API clients).
    """
    client_ip = _get_real_client_ip(request)
    tokens = auth_service.register(db, req, client_ip)

    # Set httpOnly cookies (recommended for web)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    # Return tokens in body for API clients
    return tokens


@router.post("/login", response_model=TokenResponse)
def login(
    response: Response,
    req: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    """Login and set authentication cookies.

    Returns tokens in both Cookie (httpOnly) and JSON body (for API clients).
    """
    tokens = auth_service.login(db, req)

    # Set httpOnly cookies (recommended for web)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    # Return tokens in body for API clients
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    req: RefreshRequest | None = None,
    refresh_token_cookie: str = Depends(get_refresh_token_from_cookie),
    db: Session = Depends(get_db),
):
    """Refresh access token.

    Supports dual-mode:
    - Cookie mode: refresh_token from httpOnly cookie (recommended)
    - Body mode: refresh_token from JSON body (for API clients)

    If both provided, Cookie takes priority.
    """
    # Use Cookie if available, fallback to body
    refresh_token = refresh_token_cookie or (req.refresh_token if req else None)

    if not refresh_token:
        raise ValueError("缺少刷新令牌")

    tokens = auth_service.refresh_token(db, refresh_token)

    # Update cookies
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    return tokens


@router.post("/family/join", response_model=TokenResponse)
def join_family(
    response: Response,
    req: JoinFamilyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    """Join an existing family and set authentication cookies."""
    tokens = auth_service.join_family(db, req)

    # Set httpOnly cookies
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    return tokens


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user_from_cookie),
):
    """Logout and clear authentication cookies.

    Requires Cookie-based auth (cannot logout via Bearer token).
    This prevents malicious scripts from logging out users.
    """
    clear_auth_cookies(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    req: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update user profile."""
    return auth_service.update_profile(db, user, req)


@router.put("/me/settings", response_model=UserResponse)
def update_settings(
    req: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新用户设置（主题、语言、币种、视图模式）"""
    if req.theme is not None:
        user.theme = req.theme
    if req.language is not None:
        user.language = req.language
    if req.default_currency is not None:
        user.default_currency = req.default_currency
    if req.view_mode is not None:
        user.view_mode = req.view_mode
    db.commit()
    db.refresh(user)
    return user