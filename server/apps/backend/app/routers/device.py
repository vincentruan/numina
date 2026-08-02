"""Device trust management endpoints."""

import jwt
from fastapi import APIRouter, Cookie, Depends, Request, Response
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from apps.backend.app.auth.cookies import clear_auth_cookies, clear_child_auth_cookies
from apps.backend.app.auth.deps import (
    ACCESS_TOKEN_COOKIE,
    ALGORITHM,
    CHILD_ACCESS_TOKEN_COOKIE,
    CHILD_REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    _verify_token,
    create_child_refresh_token,
    create_refresh_token,
)
from apps.backend.app.auth.revoke_jti import revoke_jti
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.middleware.rate_limit import _get_real_client_ip
from apps.backend.app.schemas.device import (
    DeviceCheckRequest,
    DeviceCheckResponse,
    DeviceCheckUserItem,
    DeviceSelectRequest,
    DeviceSelectResponse,
    DeviceSessionResponse,
    DeviceTrustRequest,
    DeviceTrustResponse,
    DeviceTrustWebAuthnOptionsResponse,
    DeviceTrustWebAuthnRegisterRequest,
    DeviceWebAuthnAuthOptionsRequest,
    DeviceWebAuthnAuthOptionsResponse,
    DeviceWebAuthnVerifyRequest,
    DeviceWebAuthnVerifyResponse,
    FamilyDeviceResponse,
)
from apps.backend.app.services import device as device_service
from packages.core.roles import UserRole

router = APIRouter(prefix="/auth", tags=["device"])


def _parse_device_name(request: Request) -> str:
    """Parse User-Agent header into a human-readable device name."""
    from user_agents import parse

    ua_string = request.headers.get("user-agent", "")
    ua = parse(ua_string)
    device = ua.device.family
    browser = ua.browser.family
    os = ua.os.family
    if device and device != "Other":
        name = f"{device} · {browser}"
    else:
        name = f"{os} · {browser}"
    return name or "未知设备"


def _get_jti_from_token(token: str) -> str | None:
    """Decode a JWT and return its JTI claim, or None if missing/invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("jti")
    except PyJWTError:
        return None


def _get_refresh_jti_from_cookie(
    refresh_token_cookie: str | None,
    child_refresh_token_cookie: str | None,
) -> str | None:
    """Extract JTI from whichever refresh cookie is present. Returns None if not found."""
    for cookie in (refresh_token_cookie, child_refresh_token_cookie):
        if cookie:
            jti = _get_jti_from_token(cookie)
            if jti:
                return jti
    return None


def _get_user_payload(
    access_token_cookie: str | None,
    child_access_token_cookie: str | None,
    request: Request,
) -> dict:
    """Verify access token from cookie or Bearer header and return its payload."""
    payload = None
    if access_token_cookie:
        payload = _verify_token(access_token_cookie, "access")
    if payload is None and child_access_token_cookie:
        payload = _verify_token(child_access_token_cookie, "access")
    # Fallback: Bearer token in Authorization header
    if payload is None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _verify_token(token, "access")
    if payload is None:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)
    return payload


@router.post("/device/trust")
def trust_device(
    request: Request,
    response: Response,
    body: DeviceTrustRequest | None = None,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(
        None, alias=CHILD_REFRESH_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """Trust the current device — issue 30-day refresh token and create/reuse DeviceSession."""
    body_device_id: str | None = body.device_id if body else None
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    family_id = int(payload["fid"])
    role = payload["role"]

    old_jti = _get_refresh_jti_from_cookie(
        refresh_token_cookie, child_refresh_token_cookie
    )

    claims = {"sub": str(user_id), "fid": str(family_id), "role": role}
    if role == UserRole.CHILD:
        new_refresh = create_child_refresh_token(claims)
    else:
        new_refresh = create_refresh_token(claims)

    new_jti = _get_jti_from_token(new_refresh)
    if new_jti is None:
        raise AppError(ErrorCode.INTERNAL_ERROR)

    if old_jti:
        revoke_jti(old_jti, ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    device_name = _parse_device_name(request)
    session, _is_new = device_service.trust_or_reuse_device(
        db,
        user_id=user_id,
        family_id=family_id,
        refresh_jti=new_jti,
        device_name=device_name,
        device_id=body_device_id,
    )

    # Set device_id cookie — not httpOnly so JS can read it for /device/check
    response.set_cookie(
        key="numina_device_id",
        value=session.device_id or "",
        max_age=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )

    cookie_name = (
        CHILD_REFRESH_TOKEN_COOKIE if role == UserRole.CHILD else REFRESH_TOKEN_COOKIE
    )
    response.set_cookie(
        key=cookie_name,
        value=new_refresh,
        max_age=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )

    return DeviceTrustResponse(
        session_id=session.id,
        device_id=session.device_id or "",
        device_name=session.device_name,
        expires_at=session.expires_at,
    )


@router.post(
    "/device/trust/webauthn/register-options",
    response_model=DeviceTrustWebAuthnOptionsResponse,
)
def device_trust_webauthn_register_options(
    request: Request,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """Generate WebAuthn registration options for the authenticated user."""
    import json as json_module

    from apps.backend.app.auth.webauthn import generate_registration_challenge
    from apps.backend.app.models.user import User

    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    existing = json_module.loads(user.webauthn_credentials or "[]")
    options = generate_registration_challenge(
        user_id=str(user.id),
        display_name=user.display_name,
        existing_credentials=existing,
    )
    challenge = options.get("challenge", "")
    return DeviceTrustWebAuthnOptionsResponse(options=options, challenge=challenge)


@router.post("/device/trust/webauthn/register")
def device_trust_webauthn_register(
    req: DeviceTrustWebAuthnRegisterRequest,
    request: Request,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """Complete WebAuthn registration — store credential on user."""
    import base64
    import json as json_module

    from apps.backend.app.auth.webauthn import verify_registration
    from apps.backend.app.models.user import User

    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    expected_challenge = base64.urlsafe_b64decode(req.challenge + "==")
    try:
        verified = verify_registration(
            credential=req.credential,
            expected_challenge=expected_challenge,
        )
    except Exception:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS) from None

    existing = json_module.loads(user.webauthn_credentials or "[]")
    existing.append(verified)
    user.webauthn_credentials = json_module.dumps(existing)
    db.commit()

    return {"registered": True}


@router.get("/devices")
def list_devices(
    request: Request,
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(
        None, alias=CHILD_REFRESH_TOKEN_COOKIE
    ),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """List trusted devices for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    current_jti = _get_refresh_jti_from_cookie(
        refresh_token_cookie, child_refresh_token_cookie
    )

    sessions = device_service.list_device_sessions(db, user_id=user_id)
    return [
        DeviceSessionResponse(
            session_id=s.id,
            device_id=s.device_id,
            device_name=s.device_name,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            is_current=(s.refresh_jti == current_jti),
        )
        for s in sessions
    ]


@router.delete("/devices/{session_id}")
def revoke_device(
    session_id: str,
    request: Request,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(
        None, alias=CHILD_REFRESH_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """Revoke a specific trusted device session."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    role = payload["role"]

    session = device_service.revoke_device_session(
        db, device_id=int(session_id), user_id=user_id
    )
    revoke_jti(
        session.refresh_jti, ttl_seconds=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600
    )

    current_jti = _get_refresh_jti_from_cookie(
        refresh_token_cookie, child_refresh_token_cookie
    )
    if current_jti == session.refresh_jti:
        if role == UserRole.CHILD:
            clear_child_auth_cookies(response)
        else:
            clear_auth_cookies(response)

    return None


@router.delete("/devices")
def revoke_all_devices(
    request: Request,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """Revoke all trusted device sessions for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    role = payload["role"]

    jtis = device_service.revoke_all_device_sessions(db, user_id=user_id)
    for jti in jtis:
        revoke_jti(jti, ttl_seconds=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600)

    if role == UserRole.CHILD:
        clear_child_auth_cookies(response)
    else:
        clear_auth_cookies(response)

    return None


_DEVICE_CHECK_RATE_LIMIT_PER_MINUTE = 20


def _check_device_check_rate_limit(ip: str) -> None:
    """Limit /device/check to 20 requests per minute per IP."""
    from packages.core.logging import get_logger

    logger = get_logger(__name__)
    try:
        from apps.backend.app.services.cache.factory import get_rate_limit_cache

        cache = get_rate_limit_cache()
        key = f"device_check:{ip}"
        count = cache.get(key)
        if count is not None and int(count) >= _DEVICE_CHECK_RATE_LIMIT_PER_MINUTE:
            raise AppError(ErrorCode.RATE_LIMITED)
        new_count = cache.increment(key)
        if new_count == 1:
            cache.set(key, 1, ttl_seconds=60)
    except AppError:
        raise
    except Exception:
        logger.warning("device_check rate limit cache unavailable, failing closed")
        raise AppError(ErrorCode.RATE_LIMITED) from None


@router.post("/device/check", response_model=DeviceCheckResponse)
def check_device(
    req: DeviceCheckRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Check if a device_id is trusted. Returns all bound users (max 6).

    No auth required — used before login. Rate-limited by IP (20/min).
    """
    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    from datetime import datetime

    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User

    now = datetime.utcnow()
    sessions = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .order_by(DeviceSession.last_seen_at.desc())
        .limit(6)
        .all()
    )

    if not sessions:
        return DeviceCheckResponse(trusted=False)

    user_ids = [s.user_id for s in sessions]
    users = db.query(User).filter(User.id.in_(user_ids), User.is_active.is_(True)).all()
    user_map = {u.id: u for u in users}

    # Fetch family names for all bound users
    family_ids = {u.family_id for u in users if u.family_id}
    families = db.query(Family).filter(Family.id.in_(family_ids)).all() if family_ids else []
    family_map = {f.id: (f.custom_title or f.name) for f in families}

    items: list[DeviceCheckUserItem] = []
    seen_user_ids: set[int] = set()
    for s in sessions:
        if s.user_id in seen_user_ids:
            continue
        user = user_map.get(s.user_id)
        if not user:
            continue
        seen_user_ids.add(s.user_id)

        if user.role == UserRole.CHILD and user.pin_hash:
            second_factor_type = "emoji_pin"
        elif user.second_factor_enabled and user.second_factor_type:
            second_factor_type = user.second_factor_type
        else:
            second_factor_type = None

        has_passkey = bool(
            user.webauthn_credentials
            and user.webauthn_credentials.strip() not in ("", "[]")
        )

        items.append(
            DeviceCheckUserItem(
                user_id=user.id,
                display_name=user.display_name,
                username=user.username,
                family_name=family_map.get(user.family_id, ""),
                avatar_color=user.avatar_color,
                role=user.role,
                second_factor_type=second_factor_type,
                has_passkey=has_passkey,
                last_seen_at=s.last_seen_at,
            )
        )

    if not items:
        return DeviceCheckResponse(trusted=False)

    return DeviceCheckResponse(trusted=True, users=items)


@router.post("/device/select", response_model=DeviceSelectResponse)
def select_device(
    req: DeviceSelectRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Select a user from device-bound accounts. No captcha required — device trust is the security proof.

    If user has second factor: returns temp_token for PIN step.
    If no second factor: sets auth cookies and returns directly.
    """
    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    from datetime import datetime, timedelta

    from apps.backend.app.auth.cookies import set_auth_cookies
    from apps.backend.app.auth.deps import (
        create_access_token,
        create_refresh_token,
        create_temp_token,
    )
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    now = datetime.utcnow()
    user_id = int(req.user_id)

    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    # Refresh session last_seen_at + expires_at (rolling window)
    session.last_seen_at = now
    session.expires_at = now + timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)
    db.commit()

    # Determine second factor
    if user.role == UserRole.CHILD and user.pin_hash:
        second_factor_type = "emoji_pin"
    elif user.second_factor_enabled and user.second_factor_type:
        second_factor_type = user.second_factor_type
    else:
        second_factor_type = None

    if second_factor_type:
        temp_token = create_temp_token(user.id, user.role)
        return DeviceSelectResponse(
            second_factor_required=True,
            temp_token=temp_token,
            second_factor_type=second_factor_type,
            display_name=user.display_name,
            avatar_color=user.avatar_color,
        )

    # No second factor — issue tokens directly
    claims = {"sub": str(user.id), "fid": str(user.family_id), "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    set_auth_cookies(response, access_token, refresh_token)

    return DeviceSelectResponse(second_factor_required=False)


@router.post(
    "/device/webauthn/auth-options", response_model=DeviceWebAuthnAuthOptionsResponse
)
def device_webauthn_auth_options(
    req: DeviceWebAuthnAuthOptionsRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate WebAuthn authentication challenge for device-bound user.

    No auth required — used in Step 0 before login. Rate-limited by IP.
    """
    import json as json_module
    from datetime import datetime

    from apps.backend.app.auth.webauthn import generate_authentication_challenge
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    now = datetime.utcnow()
    user_id = int(req.user_id)

    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    credentials = json_module.loads(user.webauthn_credentials or "[]")
    if not credentials:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    options = generate_authentication_challenge(credentials)
    challenge = options.get("challenge", "")

    return DeviceWebAuthnAuthOptionsResponse(options=options, challenge=challenge)


@router.post("/device/webauthn/verify", response_model=DeviceWebAuthnVerifyResponse)
def device_webauthn_verify(
    req: DeviceWebAuthnVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Verify WebAuthn authentication — replaces ALTCHA for passkey-enabled users.

    On success: same behavior as /device/select (issue tokens or temp_token).
    No ALTCHA required — biometric IS the proof of presence.
    """
    import base64
    import json as json_module
    from datetime import datetime, timedelta

    from apps.backend.app.auth.cookies import set_auth_cookies
    from apps.backend.app.auth.deps import (
        create_access_token,
        create_refresh_token,
        create_temp_token,
    )
    from apps.backend.app.auth.webauthn import verify_authentication
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    now = datetime.utcnow()
    user_id = int(req.user_id)

    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    credentials = json_module.loads(user.webauthn_credentials or "[]")
    credential_id = req.credential.get("id", "")
    matched = next((c for c in credentials if c["id"] == credential_id), None)
    if not matched:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    expected_challenge = base64.urlsafe_b64decode(req.challenge + "==")
    try:
        result = verify_authentication(
            credential=req.credential,
            expected_challenge=expected_challenge,
            credential_public_key=bytes.fromhex(matched["public_key"]),
            credential_current_sign_count=matched["sign_count"],
        )
    except Exception:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS) from None

    matched["sign_count"] = result["new_sign_count"]
    user.webauthn_credentials = json_module.dumps(credentials)

    session.last_seen_at = now
    session.expires_at = now + timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)
    db.commit()

    if user.role == UserRole.CHILD and user.pin_hash:
        second_factor_type = "emoji_pin"
    elif user.second_factor_enabled and user.second_factor_type:
        second_factor_type = user.second_factor_type
    else:
        second_factor_type = None

    if second_factor_type:
        temp_token = create_temp_token(user.id, user.role)
        return DeviceWebAuthnVerifyResponse(
            second_factor_required=True,
            temp_token=temp_token,
            second_factor_type=second_factor_type,
            display_name=user.display_name,
            avatar_color=user.avatar_color,
        )

    # No second factor — issue tokens directly
    claims = {"sub": str(user.id), "fid": str(user.family_id), "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    set_auth_cookies(response, access_token, refresh_token)

    return DeviceWebAuthnVerifyResponse(second_factor_required=False)


@router.get("/devices/family", response_model=list[FamilyDeviceResponse])
def list_family_devices(
    request: Request,
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(
        None, alias=CHILD_REFRESH_TOKEN_COOKIE
    ),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(
        None, alias=CHILD_ACCESS_TOKEN_COOKIE
    ),
    db: Session = Depends(get_db),
):
    """List active device sessions for all other family members. Owner only."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    role = payload["role"]
    if role != UserRole.OWNER:
        raise AppError(ErrorCode.FORBIDDEN)

    user_id = int(payload["sub"])
    family_id = int(payload["fid"])
    current_jti = _get_refresh_jti_from_cookie(
        refresh_token_cookie, child_refresh_token_cookie
    )

    rows = device_service.list_family_device_sessions(
        db,
        family_id=family_id,
        current_user_id=user_id,
        current_refresh_jti=current_jti,
    )
    return [FamilyDeviceResponse(**row) for row in rows]


@router.get("/device-ping", include_in_schema=False)
def device_ping(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """ETag-based device ID recovery endpoint.

    When all client-side storage (cookie, localStorage, IndexedDB) is cleared,
    the browser's HTTP cache may still have the ETag from a previous trust response.
    This endpoint extracts the device_id from the If-None-Match header, validates
    it against the database, and returns it if valid, allowing the client to
    recover and repopulate all storage layers.
    """
    if_none_match = request.headers.get("if-none-match")

    if if_none_match:
        # Extract device_id from ETag (format: "device-id" or W/"device-id")
        device_id = if_none_match.strip()
        if device_id.startswith("W/"):
            device_id = device_id[2:]
        device_id = device_id.strip('"')

        if device_id:
            # Validate device_id exists in database and is active
            from datetime import datetime

            from apps.backend.app.models.device_session import DeviceSession

            now = datetime.utcnow()
            valid_session = (
                db.query(DeviceSession)
                .filter(
                    DeviceSession.device_id == device_id,
                    DeviceSession.is_revoked.is_(False),
                    DeviceSession.expires_at > now,
                )
                .first()
            )

            if valid_session:
                # Return the device_id with ETag header to maintain cache
                response.headers["ETag"] = f'"{device_id}"'
                response.headers["Cache-Control"] = (
                    "private, max-age=2592000"  # 30 days
                )
                return {"device_id": device_id}

    # No valid ETag found or device_id not valid
    response.headers["Cache-Control"] = "no-store"
    return {"device_id": None}
