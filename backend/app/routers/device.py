"""Device trust management endpoints."""

from fastapi import APIRouter, Cookie, Depends, Request, Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.cookies import clear_auth_cookies, clear_child_auth_cookies
from app.auth.deps import (
    ACCESS_TOKEN_COOKIE,
    ALGORITHM,
    CHILD_ACCESS_TOKEN_COOKIE,
    CHILD_REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    _verify_token,
    create_child_refresh_token,
    create_refresh_token,
)
from app.auth.revoke_jti import revoke_jti
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.schemas.device import (
    DeviceCheckRequest,
    DeviceCheckResponse,
    DeviceSessionResponse,
    DeviceTrustRequest,
    DeviceTrustResponse,
    FamilyDeviceResponse,
)
from app.services import device as device_service

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
    except JWTError:
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
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Trust the current device — issue 30-day refresh token and create DeviceSession.

    Optionally accepts a browser fingerprint to enable fingerprint-based device detection.
    """
    body_fingerprint: str | None = body.fingerprint if body else None
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    family_id = int(payload["fid"])
    role = payload["role"]

    old_jti = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)

    claims = {"sub": str(user_id), "fid": str(family_id), "role": role}
    if role == "child":
        new_refresh = create_child_refresh_token(claims)
    else:
        new_refresh = create_refresh_token(claims)

    new_jti = _get_jti_from_token(new_refresh)
    if new_jti is None:
        raise AppError(ErrorCode.INTERNAL_ERROR)

    if old_jti:
        revoke_jti(old_jti, ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    device_name = _parse_device_name(request)
    session = device_service.create_device_session(
        db,
        user_id=user_id,
        family_id=family_id,
        refresh_jti=new_jti,
        device_name=device_name,
        browser_fingerprint=body_fingerprint,
    )

    cookie_name = CHILD_REFRESH_TOKEN_COOKIE if role == "child" else REFRESH_TOKEN_COOKIE
    response.set_cookie(
        key=cookie_name,
        value=new_refresh,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )

    return DeviceTrustResponse(
        device_id=str(session.id),
        device_name=session.device_name,
        expires_at=session.expires_at,
    )


@router.get("/devices")
def list_devices(
    request: Request,
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """List trusted devices for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    current_jti = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)

    sessions = device_service.list_device_sessions(db, user_id=user_id)
    return [
        DeviceSessionResponse(
            id=str(s.id),
            device_name=s.device_name,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            is_current=(s.refresh_jti == current_jti),
        )
        for s in sessions
    ]


@router.delete("/devices/{device_id}")
def revoke_device(
    device_id: str,
    request: Request,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Revoke a specific trusted device session."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    role = payload["role"]

    session = device_service.revoke_device_session(
        db, device_id=int(device_id), user_id=user_id
    )
    revoke_jti(session.refresh_jti, ttl_seconds=30 * 24 * 3600)

    current_jti = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)
    if current_jti == session.refresh_jti:
        if role == "child":
            clear_child_auth_cookies(response)
        else:
            clear_auth_cookies(response)

    return None


@router.delete("/devices")
def revoke_all_devices(
    request: Request,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Revoke all trusted device sessions for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])
    role = payload["role"]

    jtis = device_service.revoke_all_device_sessions(db, user_id=user_id)
    for jti in jtis:
        revoke_jti(jti, ttl_seconds=30 * 24 * 3600)

    if role == "child":
        clear_child_auth_cookies(response)
    else:
        clear_auth_cookies(response)

    return None


@router.post("/device/check", response_model=DeviceCheckResponse)
def check_device(
    req: DeviceCheckRequest,
    db: Session = Depends(get_db),
):
    """Check if a device fingerprint is trusted. No auth required — used before login.

    When trusted, loads the associated user and returns a temp_token so the
    frontend can skip Step 1 of the two-step login flow entirely.
    """
    from datetime import datetime

    from app.auth.deps import create_temp_token
    from app.models.device_session import DeviceSession
    from app.models.user import User

    now = datetime.utcnow()
    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.browser_fingerprint == req.fingerprint,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        return DeviceCheckResponse(trusted=False)

    user = db.query(User).filter(
        User.id == session.user_id,
        User.is_active.is_(True),
    ).first()
    if not user:
        return DeviceCheckResponse(trusted=False)

    temp_token = create_temp_token(user.id, user.role)

    # Determine second factor type correctly for children (who use pin_hash)
    # vs adults (who use configured second_factor_type)
    if user.role == "child" and user.pin_hash:
        second_factor_type = "emoji_pin"
    elif user.second_factor_enabled and user.second_factor_type:
        second_factor_type = user.second_factor_type
    else:
        second_factor_type = None

    return DeviceCheckResponse(
        trusted=True,
        device_name=session.device_name,
        user_id=user.id,
        temp_token=temp_token,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        second_factor_type=second_factor_type,
    )


@router.get("/devices/family", response_model=list[FamilyDeviceResponse])
def list_family_devices(
    request: Request,
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """List active device sessions for all other family members. Owner or admin only."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    role = payload["role"]
    if role not in ("owner", "admin"):
        raise AppError(ErrorCode.FORBIDDEN)

    user_id = int(payload["sub"])
    family_id = int(payload["fid"])
    current_jti = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)

    rows = device_service.list_family_device_sessions(
        db,
        family_id=family_id,
        current_user_id=user_id,
        current_refresh_jti=current_jti,
    )
    return [FamilyDeviceResponse(**row) for row in rows]
