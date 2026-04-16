"""Child account management service."""

import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.child_bind_token import ChildBindToken
from app.models.family import Family
from app.models.user import User
from app.schemas.children import CreateChildRequest, UpdateChildRequest


def _hash_pin(pin_sequence: list[str]) -> str:
    """NFC-normalize and bcrypt-hash a 4-emoji PIN sequence."""
    try:
        from app.config import settings

        rounds = settings.PIN_BCRYPT_ROUNDS
    except (ImportError, AttributeError):
        rounds = 10
    normalized = unicodedata.normalize("NFC", "".join(pin_sequence))
    return bcrypt.hashpw(
        normalized.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")


def create_child(db: Session, family_id: str, req: CreateChildRequest) -> User:
    user = User(
        id=str(uuid4()),
        family_id=family_id,
        username=None,
        display_name=req.display_name,
        avatar_color=req.avatar_color,
        password_hash=None,
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
        .filter(
            User.family_id == family_id, User.role == "child", User.is_active
        )
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
            status_code=status.HTTP_404_NOT_FOUND, detail="子账号不存在"
        )
    if req.display_name is not None:
        child.display_name = req.display_name
    if req.avatar_color is not None:
        child.avatar_color = req.avatar_color
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
            status_code=status.HTTP_404_NOT_FOUND, detail="子账号不存在"
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
            status_code=status.HTTP_404_NOT_FOUND, detail="子账号不存在"
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
            status_code=status.HTTP_404_NOT_FOUND, detail="子账号不存在"
        )
    child.token_version = (child.token_version or 0) + 1
    db.commit()


def create_bind_token(db: Session, family_id: str) -> ChildBindToken:
    token = ChildBindToken(
        id=str(uuid4()),
        family_id=family_id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24),
        used=False,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_bind_info(db: Session, token_str: str) -> tuple[Family, list[User]]:
    bind_token = (
        db.query(ChildBindToken).filter(ChildBindToken.token == token_str).first()
    )
    if not bind_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的绑定令牌"
        )
    now = datetime.now(UTC).replace(tzinfo=None)
    if bind_token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="绑定令牌已过期"
        )
    if bind_token.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="绑定令牌已使用"
        )
    bind_token.used = True
    db.commit()
    family = db.query(Family).filter(Family.id == bind_token.family_id).first()
    children = (
        db.query(User)
        .filter(
            User.family_id == bind_token.family_id,
            User.role == "child",
            User.is_active,
        )
        .all()
    )
    return family, children
