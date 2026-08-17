"""Child account management service."""

import unicodedata

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from apps.backend.app.schemas.children import CreateChildRequest, UpdateChildRequest


def _hash_pin(pin_sequence: list[str]) -> str:
    """NFC-normalize and bcrypt-hash a 4-emoji PIN sequence."""
    try:
        from apps.backend.app.config import settings

        rounds = settings.PIN_BCRYPT_ROUNDS
    except (ImportError, AttributeError):
        rounds = 10
    normalized = unicodedata.normalize("NFC", "".join(pin_sequence))
    return bcrypt.hashpw(
        normalized.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")


def create_child(db: Session, family_id: str, req: CreateChildRequest) -> User:
    # 检查 username 全局唯一
    existing = db.query(User).filter(User.username == req.username.lower()).first()
    if existing:
        from apps.backend.app.errors import AppError, ErrorCode

        raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)

    try:
        from apps.backend.app.config import settings
        rounds = settings.BCRYPT_ROUNDS
    except (ImportError, AttributeError):
        rounds = 12

    user = User(
        family_id=family_id,
        username=req.username.lower(),
        display_name=req.display_name,
        avatar_color=req.avatar_color,
        password_hash=bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8"),
        role="child",
        pin_hash=_hash_pin(req.pin),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_children(db: Session, family_id: str) -> list[User]:
    return (
        db.query(User)
        .filter(User.family_id == family_id, User.role == "child", User.is_active)
        .all()
    )


def update_child(
    db: Session, child_id: str, family_id: str, req: UpdateChildRequest
) -> User:
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == family_id, User.role == "child")
        .first()
    )
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CHILD_ACCOUNT_NOT_FOUND", "message": "子账号不存在"}
        )
    if req.username is not None:
        # 检查 username 全局唯一（排除自己）
        existing = (
            db.query(User)
            .filter(User.username == req.username.lower(), User.id != child_id)
            .first()
        )
        if existing:
            from apps.backend.app.errors import AppError, ErrorCode

            raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)
        child.username = req.username.lower()
    if req.display_name is not None:
        child.display_name = req.display_name
    if req.avatar_color is not None:
        child.avatar_color = req.avatar_color
    # Use model_fields_set to distinguish "not provided" from "explicitly cleared"
    if "avatar_url" in req.model_fields_set:
        child.avatar_url = req.avatar_url
    if req.pin is not None:
        child.pin_hash = _hash_pin(req.pin)
        child.pin_fail_count = 0
        child.pin_locked_until = None
    db.commit()
    db.refresh(child)
    return child


def deactivate_child(db: Session, child_id: str, family_id: str) -> None:
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == family_id, User.role == "child")
        .first()
    )
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CHILD_ACCOUNT_NOT_FOUND", "message": "子账号不存在"}
        )
    child.is_active = False
    db.commit()


def unlock_child_pin(db: Session, child_id: str, family_id: str) -> None:
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == family_id, User.role == "child")
        .first()
    )
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CHILD_ACCOUNT_NOT_FOUND", "message": "子账号不存在"}
        )
    child.pin_locked_until = None
    child.pin_fail_count = 0
    db.commit()


def force_logout_child(db: Session, child_id: str, family_id: str) -> None:
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == family_id, User.role == "child")
        .first()
    )
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CHILD_ACCOUNT_NOT_FOUND", "message": "子账号不存在"}
        )
    child.token_version = (child.token_version or 0) + 1
    db.commit()
