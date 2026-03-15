import time
from uuid import uuid4

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import create_access_token, create_refresh_token
from app.models.family import Family, generate_invite_code
from app.models.user import User
from app.schemas.auth import (
    JoinFamilyRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)

# Login rate limiting: {username: (fail_count, first_fail_time)}
_login_attempts: dict[str, tuple[int, float]] = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _check_rate_limit(username: str) -> None:
    if username not in _login_attempts:
        return
    count, first_time = _login_attempts[username]
    if count >= _MAX_ATTEMPTS:
        elapsed = time.time() - first_time
        if elapsed < _LOCKOUT_SECONDS:
            remaining = int((_LOCKOUT_SECONDS - elapsed) / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录失败次数过多，请 {remaining} 分钟后重试",
            )
        # Lockout expired, reset
        del _login_attempts[username]


def _record_failed_login(username: str) -> None:
    if username in _login_attempts:
        count, first_time = _login_attempts[username]
        _login_attempts[username] = (count + 1, first_time)
    else:
        _login_attempts[username] = (1, time.time())


def _clear_failed_login(username: str) -> None:
    _login_attempts.pop(username, None)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def register(db: Session, req: RegisterRequest) -> TokenResponse:
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    family_id = str(uuid4())
    user_id = str(uuid4())

    family = Family(
        id=family_id,
        name=req.family_name,
        created_by=user_id,
    )
    db.add(family)

    user = User(
        id=user_id,
        family_id=family_id,
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="owner",
    )
    db.add(user)
    db.commit()

    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def login(db: Session, req: LoginRequest) -> TokenResponse:
    _check_rate_limit(req.username)

    user = db.query(User).filter(User.username == req.username, User.is_active == True).first()
    if not user or not verify_password(req.password, user.password_hash):
        _record_failed_login(req.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    _clear_failed_login(req.username)
    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def refresh_token(db: Session, refresh_tok: str) -> TokenResponse:
    from jose import JWTError, jwt
    from app.config import settings
    from app.auth.deps import ALGORITHM

    try:
        payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def join_family(db: Session, req: JoinFamilyRequest) -> TokenResponse:
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    family = db.query(Family).filter(Family.invite_code == req.invite_code).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请码无效")

    user = User(
        family_id=family.id,
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=create_refresh_token({"sub": user.id}),
    )


def update_profile(db: Session, user: User, req: UpdateProfileRequest) -> User:
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.avatar_color is not None:
        user.avatar_color = req.avatar_color
    db.commit()
    db.refresh(user)
    return user
