"""用户和家庭工厂 — 幂等创建，按 username 查重。"""

from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Optional

from bcrypt import checkpw, hashpw, gensalt
from sqlalchemy.orm import Session

from models import Family, User


def _hash(password: str) -> str:
    return hashpw(password.encode(), gensalt()).decode()


def _invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# Simple monotonic ID generator for standalone scripts (not Snowflake, just unique enough)
_id_counter = int(datetime.utcnow().timestamp() * 1000) << 10


def next_id() -> int:
    global _id_counter
    _id_counter += 1
    return _id_counter


class FamilyFactory:
    @staticmethod
    def get_or_create(db: Session, *, name: str, created_by_id: int, family_id: int | None = None) -> Family:
        if family_id:
            existing = db.get(Family, family_id)
            if existing:
                return existing
        fam = Family(
            id=family_id or next_id(),
            name=name,
            invite_code=_invite_code(),
            created_by=created_by_id,
        )
        db.add(fam)
        db.flush()
        return fam


class UserFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        username: str,
        display_name: str,
        password: str,
        family_id: int,
        role: str = "owner",
        avatar_color: str = "#4F46E5",
        flush: bool = True,
    ) -> tuple[User, bool]:
        """Returns (user, created). created=False means it already existed.

        On re-seed (existing user), password is re-hashed to keep it consistent
        with the seed definition.  This avoids stale credentials when the DB
        persists across container rebuilds (e.g. bind-mounted SQLite).

        `flush=False` is useful when creating the first owner of a new family:
        the family must be created after the user (to know the user id) but the
        user's family_id can only be set after the family exists.  Callers must
        flush the session themselves once both objects are wired together.
        """
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            existing.password_hash = _hash(password)
            return existing, False
        user = User(
            id=next_id(),
            family_id=family_id,
            username=username,
            display_name=display_name,
            password_hash=_hash(password),
            role=role,
            avatar_color=avatar_color,
        )
        db.add(user)
        if flush:
            db.flush()
        return user, True

    @staticmethod
    def get_or_create_child(
        db: Session,
        *,
        display_name: str,
        family_id: int,
        username: str | None = None,
        password: str = "DemoPass123",
        pin: str | None = None,
        avatar_color: str = "#FF6B6B",
    ) -> tuple[User, bool]:
        """Child accounts have role='child', optional username, required password, optional PIN.

        On re-seed (existing user), password and PIN are re-hashed to keep them
        consistent with the seed definition.  This avoids stale credentials when
        the DB persists across container rebuilds (e.g. bind-mounted SQLite).
        """
        existing = (
            db.query(User)
            .filter(User.family_id == family_id, User.display_name == display_name, User.role == "child")
            .first()
        )
        if existing:
            existing.password_hash = _hash(password)
            if pin is not None:
                existing.pin_hash = _hash(pin)
            if username is not None:
                existing.username = username.lower()
            return existing, False
        child = User(
            id=next_id(),
            family_id=family_id,
            username=username.lower() if username else None,
            display_name=display_name,
            password_hash=_hash(password),
            role="child",
            avatar_color=avatar_color,
            pin_hash=_hash(pin) if pin else None,
        )
        db.add(child)
        db.flush()
        return child, True
