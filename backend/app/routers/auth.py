"""Authentication endpoints with Cookie-based auth support.

Dual-mode authentication:
- Cookie mode: Recommended for web browsers (XSS-resistant)
- Bearer mode: For API clients (mobile apps, CLI tools)

Cookie is set automatically on login/register, Bearer token still returned
in response body for backward compatibility.
"""

import base64
import json

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.captcha import verify_captcha
from app.auth.cookies import (
    clear_auth_cookies,
    clear_child_auth_cookies,
    set_auth_cookies,
    set_child_auth_cookies,
)
from app.auth.deps import (
    get_child_refresh_token_from_cookie,
    get_current_child_user,
    get_current_user,
    get_current_user_from_cookie,
    get_refresh_token_from_cookie,
    require_owner,
)
from app.database import get_db
from app.errors.codes import ErrorCode
from app.errors.exceptions import AppError
from app.middleware.rate_limit import _get_real_client_ip
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChildPinLoginRequest,
    ChildRefreshResponse,
    JoinFamilyRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UpdateSettingsRequest,
    UserResponse,
    VerifyParentPasswordRequest,
)
from app.auth import webauthn as webauthn_helper
from app.schemas.webauthn import (
    WebAuthnAuthenticationOptionsRequest,
    WebAuthnAuthenticationOptionsResponse,
    WebAuthnAuthenticationRequest,
    WebAuthnRegistrationOptionsRequest,
    WebAuthnRegistrationOptionsResponse,
    WebAuthnRegistrationRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _decode_webauthn_challenge(challenge: str) -> bytes:
    """Decode base64url challenge with proper padding."""
    # Add padding if needed (base64 requires length % 4 == 0)
    padding = 4 - (len(challenge) % 4)
    if padding != 4:
        challenge += '=' * padding
    return base64.urlsafe_b64decode(challenge)


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


@router.post("/me/password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """修改密码，成功后吊销该用户所有现存 token，需重新登录。"""
    auth_service.change_password(db, user, req.old_password, req.new_password)
    return {"message": "密码已修改，请重新登录"}


# ---------------------------------------------------------------------------
# Child authentication endpoints
# ---------------------------------------------------------------------------


@router.post("/child/login", response_model=TokenResponse)
def child_login(
    response: Response,
    req: ChildPinLoginRequest,
    db: Session = Depends(get_db),
):
    """Child PIN login — no captcha required.

    Sets child-specific httpOnly cookies and returns tokens in body.
    """
    tokens = auth_service.child_pin_login(db, req.child_id, req.pin_sequence)
    set_child_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.get("/child/me", response_model=UserResponse)
def get_child_me(child_user: User = Depends(get_current_child_user)):
    """Get current child user profile.

    Uses child-specific authentication dependency.
    """
    return child_user


@router.post("/child/refresh", response_model=ChildRefreshResponse)
def child_refresh(
    response: Response,
    refresh_tok: str = Depends(get_child_refresh_token_from_cookie),
    db: Session = Depends(get_db),
):
    """Refresh child access token using child refresh cookie."""
    tokens = auth_service.child_refresh_token(db, refresh_tok)
    # Only update the access token cookie; refresh token stays the same
    from app.auth.deps import CHILD_ACCESS_TOKEN_COOKIE
    from app.config import settings

    response.set_cookie(
        key=CHILD_ACCESS_TOKEN_COOKIE,
        value=tokens.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )
    return {"message": "token refreshed"}


@router.post("/child/verify-parent")
def child_verify_parent(
    req: VerifyParentPasswordRequest,
    db: Session = Depends(get_db),
    child_user: User = Depends(get_current_child_user),
):
    """Verify parent password while in child mode.

    Used to gate adult-only actions on shared devices.
    """
    auth_service.verify_parent_password(db, child_user, req.password)
    return {"message": "verified"}


@router.post("/child/logout")
def child_logout(
    response: Response,
    child_user: User = Depends(get_current_child_user),
):
    """Logout from child mode and clear child auth cookies."""
    clear_child_auth_cookies(response)
    return {"message": "已退出儿童模式"}


@router.post(
    "/child/webauthn/register-options",
    response_model=WebAuthnRegistrationOptionsResponse,
)
def child_webauthn_register_options(
    req: WebAuthnRegistrationOptionsRequest,
    db: Session = Depends(get_db),
):
    """Generate WebAuthn registration options for a child account.

    Returns challenge and options for navigator.credentials.create().
    Challenge must be stored and passed back in registration request.
    """
    child = db.query(User).filter(User.id == req.child_id, User.role == "child").first()
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    existing_creds = json.loads(child.webauthn_credentials or "[]")
    options = webauthn_helper.generate_registration_challenge(
        user_id=child.id,
        display_name=child.display_name,
        existing_credentials=existing_creds,
    )
    return WebAuthnRegistrationOptionsResponse(
        options=options, challenge=options["challenge"]
    )


@router.post("/child/webauthn/register", response_model=dict)
def child_webauthn_register(
    req: WebAuthnRegistrationRequest,
    db: Session = Depends(get_db),
):
    """Verify and store WebAuthn credential for a child account.

    Client sends credential from navigator.credentials.create().
    Credential is verified and stored in user.webauthn_credentials.
    """
    child = db.query(User).filter(User.id == req.child_id, User.role == "child").first()
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    try:
        expected_challenge = _decode_webauthn_challenge(req.challenge)
        verified_cred = webauthn_helper.verify_registration(
            credential=req.credential,
            expected_challenge=expected_challenge,
        )
    except Exception as e:
        raise AppError(ErrorCode.AUTH_WEBAUTHN_VERIFICATION_FAILED, detail=str(e))

    existing_creds = json.loads(child.webauthn_credentials or "[]")
    existing_creds.append(verified_cred)
    child.webauthn_credentials = json.dumps(existing_creds)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR, detail="Failed to store credential")

    return {"message": "passkey registered"}


@router.post(
    "/child/webauthn/login-options",
    response_model=WebAuthnAuthenticationOptionsResponse,
)
def child_webauthn_login_options(
    req: WebAuthnAuthenticationOptionsRequest,
    db: Session = Depends(get_db),
):
    """Generate WebAuthn authentication options for a child account.

    Returns challenge and allowed credentials for navigator.credentials.get().
    """
    child = db.query(User).filter(User.id == req.child_id, User.role == "child").first()
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    if not child.webauthn_credentials:
        raise AppError(ErrorCode.AUTH_NO_PASSKEY_REGISTERED)

    credentials = json.loads(child.webauthn_credentials)
    options = webauthn_helper.generate_authentication_challenge(credentials)

    return WebAuthnAuthenticationOptionsResponse(
        options=options, challenge=options["challenge"]
    )


@router.post("/child/webauthn/login", response_model=TokenResponse)
def child_webauthn_login(
    response: Response,
    req: WebAuthnAuthenticationRequest,
    db: Session = Depends(get_db),
):
    """Verify WebAuthn credential and issue child JWT tokens.

    Client sends credential from navigator.credentials.get().
    On success, returns tokens and sets child auth cookies.
    """
    child = db.query(User).filter(User.id == req.child_id, User.role == "child").first()
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    if not child.webauthn_credentials:
        raise AppError(ErrorCode.AUTH_NO_PASSKEY_REGISTERED)

    credentials = json.loads(child.webauthn_credentials)
    credential_id = req.credential["id"]

    stored_cred = next((c for c in credentials if c["id"] == credential_id), None)
    if not stored_cred:
        raise AppError(ErrorCode.AUTH_CREDENTIAL_NOT_FOUND)

    try:
        expected_challenge = _decode_webauthn_challenge(req.challenge)
        verification = webauthn_helper.verify_authentication(
            credential=req.credential,
            expected_challenge=expected_challenge,
            credential_public_key=bytes.fromhex(stored_cred["public_key"]),
            credential_current_sign_count=stored_cred["sign_count"],
        )
    except Exception as e:
        raise AppError(ErrorCode.AUTH_WEBAUTHN_VERIFICATION_FAILED, detail=str(e))

    stored_cred["sign_count"] = verification["new_sign_count"]
    child.webauthn_credentials = json.dumps(credentials)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR, detail="Failed to update credential")

    from app.auth.deps import create_access_token, create_refresh_token

    tokens = TokenResponse(
        access_token=create_access_token({"sub": child.id, "role": "child"}),
        refresh_token=create_refresh_token({"sub": child.id, "role": "child"}),
    )
    set_child_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post("/admin/switch-child/{child_id}", response_model=TokenResponse)
def admin_switch_child(
    response: Response,
    child_id: str,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """Admin switches to child view without PIN verification.

    Only family owner can use this endpoint. Returns child JWT tokens
    and sets child authentication cookies.

    Args:
        child_id: Target child ID to switch to

    Returns:
        TokenResponse with child access and refresh tokens
    """
    tokens = auth_service.admin_switch_to_child(db, owner, child_id)
    set_child_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.get("/child/bind")
def get_child_bind_info(
    token: str,
    db: Session = Depends(get_db),
):
    """Validate bind token and return family info with children.

    Used by independent child devices to get selectable accounts.
    Token is single-use — marked as used after this call.
    """
    from app.schemas.children import ChildResponse
    from app.services import children as children_service

    family, children = children_service.get_bind_info(db, token)
    return {
        "family_id": family.id,
        "family_name": family.name,
        "children": [ChildResponse.model_validate(c) for c in children],
    }


@router.get("/child/family/{family_id}/children")
def get_family_children(
    family_id: str,
    bind_token: str,
    db: Session = Depends(get_db),
):
    """Return active children for a family — requires a valid bind token.

    The bind_token must belong to the requested family_id and must not be
    expired. It may be used or unused (account-picker is called after binding).
    Only non-sensitive display fields are exposed via ChildResponse.
    Fields NOT exposed: pin_hash, pin_fail_count, pin_locked_until, token_version.
    """
    from datetime import UTC, datetime

    from fastapi import HTTPException, status

    from app.models.child_bind_token import ChildBindToken
    from app.schemas.children import ChildResponse

    token_record = (
        db.query(ChildBindToken)
        .filter(
            ChildBindToken.token == bind_token,
            ChildBindToken.family_id == family_id,
        )
        .first()
    )
    if not token_record:
        raise AppError(ErrorCode.AUTH_INVITE_CODE_INVALID)
    now = datetime.now(UTC).replace(tzinfo=None)
    if token_record.expires_at < now:
        raise AppError(ErrorCode.AUTH_INVITE_CODE_INVALID)

    children = (
        db.query(User)
        .filter(
            User.family_id == family_id, User.role == "child", User.is_active
        )
        .all()
    )
    return [ChildResponse.model_validate(c) for c in children]
