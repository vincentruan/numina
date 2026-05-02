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

from app.auth import webauthn as webauthn_helper
from app.auth.captcha import verify_captcha
from app.auth.cookies import (
    clear_auth_cookies,
    clear_child_auth_cookies,
    set_auth_cookies,
    set_child_auth_cookies,
)
from app.auth.deps import (
    create_temp_token,
    get_child_refresh_token_from_cookie,
    get_current_child_user,
    get_current_user,
    get_current_user_from_cookie,
    get_refresh_token_from_cookie,
    require_owner,
    verify_temp_token,
)
from app.database import get_db
from app.errors.codes import ErrorCode
from app.errors.exceptions import AppError
from app.middleware.rate_limit import _get_real_client_ip
from app.models.user import User
from app.schemas.auth import (
    ChangeNumericPinRequest,
    ChangePasswordRequest,
    ChildPinLoginRequest,
    ChildRefreshResponse,
    JoinFamilyRequest,
    LoginRequest,
    LoginStep1Request,
    LoginStep1Response,
    LoginStep2Request,
    RefreshRequest,
    RegisterRequest,
    SetChildPasswordRequest,
    SetupNumericPinRequest,
    TokenResponse,
    UpdateProfileRequest,
    UpdateSettingsRequest,
    UserResponse,
    VerifyParentPasswordRequest,
)
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
        challenge += "=" * padding
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


@router.post("/me/password/reset")
async def reset_password(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通过通知渠道发送临时密码重置密码。需要家庭至少配置一个通知渠道。"""
    import random
    import string

    from app.models.notification_channel import NotificationChannel
    from app.models.notification_channel_config import NotificationChannelConfig
    from app.services.notification.sender import NotificationSender

    # Check notification channels exist
    channels = (
        db.query(NotificationChannel)
        .filter_by(family_id=user.family_id, is_enabled=True)
        .all()
    )
    if not channels:
        raise AppError(ErrorCode.NOTIFICATION_NO_CHANNEL)

    # Generate temp password
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(random.choices(alphabet, k=12))

    # Hash and save
    import bcrypt

    from app.auth.revoke_jti import revoke_all_user_tokens
    from app.config import settings as app_settings

    rounds = getattr(app_settings, "BCRYPT_ROUNDS", 12)
    user_db = db.query(User).filter(User.id == user.id).first()
    user_db.password_hash = bcrypt.hashpw(
        temp_password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")
    db.commit()
    revoke_all_user_tokens(user.id)

    # Send via first available channel
    channel = channels[0]
    configs = (
        db.query(NotificationChannelConfig)
        .filter_by(channel_id=channel.id)
        .all()
    )
    cfg = {c.config_key: c.config_value for c in configs}

    message = f"【Numina】您的临时密码为：{temp_password}\n请登录后立即修改密码。"
    if channel.channel_type == "telegram":
        await NotificationSender.send_telegram(
            cfg.get("bot_token", ""),
            cfg.get("chat_id", ""),
            message,
        )
    elif channel.channel_type == "email":
        NotificationSender.send_email(
            smtp_host=cfg.get("smtp_host", ""),
            smtp_port=int(cfg.get("smtp_port", 587)),
            smtp_user=cfg.get("smtp_user", ""),
            smtp_password=cfg.get("smtp_password", ""),
            smtp_from=cfg.get("smtp_from", cfg.get("smtp_user", "")),
            to=cfg.get("to_email", ""),
            subject="【Numina】临时密码",
            body=message,
        )

    return {"message": "临时密码已发送，请重新登录"}


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

    支持双模式登录：
    - username + PIN（主要方式）
    - child_id + PIN（备选方式，向后兼容）

    Sets child-specific httpOnly cookies and returns tokens in body.
    """
    tokens = auth_service.child_pin_login(
        db, req.child_id, req.username, req.pin_sequence
    )
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
        raise AppError(ErrorCode.AUTH_WEBAUTHN_VERIFICATION_FAILED, details=str(e))

    existing_creds = json.loads(child.webauthn_credentials or "[]")
    existing_creds.append(verified_cred)
    child.webauthn_credentials = json.dumps(existing_creds)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR, details="Failed to store credential")

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
        raise AppError(ErrorCode.AUTH_WEBAUTHN_VERIFICATION_FAILED, details=str(e))

    stored_cred["sign_count"] = verification["new_sign_count"]
    child.webauthn_credentials = json.dumps(credentials)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR, details="Failed to update credential")

    from app.auth.deps import create_access_token, create_refresh_token
    from app.auth.jwt_utils import user_claims

    tokens = TokenResponse(
        access_token=create_access_token(user_claims(child)),
        refresh_token=create_refresh_token(user_claims(child)),
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


# ---------------------------------------------------------------------------
# Two-step login
# ---------------------------------------------------------------------------


@router.post("/login/step1", response_model=LoginStep1Response)
def login_step1(
    req: LoginStep1Request,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step 1: Verify username + password. Returns temp token if second factor required."""
    import bcrypt

    from app.auth.jwt_utils import user_claims

    # Find user (adult or child)
    user = db.query(User).filter(
        User.username == req.username.lower(),
        User.is_active.is_(True),
    ).first()

    # Timing attack protection
    if not user or not user.password_hash:
        dummy = auth_service._get_dummy_hash()
        bcrypt.checkpw(b"dummy", dummy.encode("utf-8"))
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    if not bcrypt.checkpw(req.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # If no second factor configured, issue tokens directly
    if not user.second_factor_enabled or not user.second_factor_type:
        from app.auth.deps import create_access_token, create_refresh_token
        access_token = create_access_token(user_claims(user))
        refresh_token = create_refresh_token(user_claims(user, token_version=user.token_version))
        if user.role == "child":
            set_child_auth_cookies(response, access_token, refresh_token)
        else:
            set_auth_cookies(response, access_token, refresh_token)
        return LoginStep1Response(
            second_factor_required=False,
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            display_name=user.display_name,
            avatar_color=user.avatar_color,
        )

    # Issue temp token for step 2
    temp_token = create_temp_token(user.id, user.role)
    return LoginStep1Response(
        temp_token=temp_token,
        second_factor_required=True,
        second_factor_type=user.second_factor_type,
        user_id=user.id,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
    )


@router.post("/login/step2", response_model=TokenResponse)
def login_step2(
    req: LoginStep2Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Step 2: Verify second factor (PIN). Returns full tokens on success."""
    from app.auth.jwt_utils import user_claims
    from app.auth.second_factor import get_strategy

    payload = verify_temp_token(req.temp_token)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    strategy = get_strategy(req.factor_type)
    if not strategy.verify(db, user, req.payload):
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    from app.auth.deps import create_access_token, create_refresh_token
    access_token = create_access_token(user_claims(user))
    refresh_token = create_refresh_token(user_claims(user, token_version=user.token_version))

    if user.role == "child":
        set_child_auth_cookies(response, access_token, refresh_token)
    else:
        set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# PIN management
# ---------------------------------------------------------------------------


@router.post("/pin/setup")
def setup_numeric_pin(
    req: SetupNumericPinRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set up numeric PIN for adult second factor."""
    import bcrypt

    from app.config import settings as app_settings

    rounds = getattr(app_settings, "PIN_BCRYPT_ROUNDS", 10)
    user_db = db.query(User).filter(User.id == user.id).first()
    if not user_db:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    user_db.numeric_pin_hash = bcrypt.hashpw(
        req.pin.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")
    user_db.second_factor_type = "numeric_pin"
    user_db.second_factor_enabled = True
    db.commit()
    return {"message": "数字PIN设置成功"}


@router.post("/pin/change")
def change_numeric_pin(
    req: ChangeNumericPinRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change numeric PIN — requires old PIN verification."""
    import bcrypt

    from app.auth.second_factor import NumericPinStrategy
    from app.config import settings as app_settings

    user_db = db.query(User).filter(User.id == user.id).first()
    if not user_db:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    strategy = NumericPinStrategy()
    if not strategy.verify(db, user_db, {"pin": req.old_pin}):
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    rounds = getattr(app_settings, "PIN_BCRYPT_ROUNDS", 10)
    user_db.numeric_pin_hash = bcrypt.hashpw(
        req.new_pin.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")
    db.commit()
    return {"message": "数字PIN修改成功"}


@router.post("/pin/disable")
def disable_numeric_pin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Disable numeric PIN second factor."""
    user_db = db.query(User).filter(User.id == user.id).first()
    if not user_db:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)
    user_db.numeric_pin_hash = None
    user_db.second_factor_type = None
    user_db.second_factor_enabled = False
    db.commit()
    return {"message": "二阶段验证已禁用"}


@router.post("/child/{child_id}/password")
def set_child_password(
    child_id: int,
    req: SetChildPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set or change a child's password. Allowed for family members (parents) or the child themselves."""
    import bcrypt

    from app.config import settings as app_settings

    child = db.query(User).filter(
        User.id == child_id,
        User.role == "child",
        User.is_active.is_(True),
    ).first()
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    # Permission: same family + (parent role or child themselves)
    if child.family_id != user.family_id:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    if user.role == "child" and user.id != child_id:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)

    rounds = getattr(app_settings, "BCRYPT_ROUNDS", 12)
    child.password_hash = bcrypt.hashpw(
        req.new_password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")
    db.commit()
    return {"message": "儿童密码设置成功"}
