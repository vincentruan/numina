from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.captcha import verify_captcha
from app.auth.deps import get_current_user
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
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    client_ip = _get_real_client_ip(request)
    return auth_service.register(db, req, client_ip)


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    return auth_service.login(db, req)


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_token(db, req.refresh_token)


@router.post("/family/join", response_model=TokenResponse)
def join_family(
    req: JoinFamilyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_captcha),
):
    return auth_service.join_family(db, req)


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    req: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
