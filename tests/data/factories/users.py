"""用户和家庭工厂 — 幂等创建，按 username 查重。"""

import random
import string
from datetime import datetime

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
    ) -> tuple[User, bool]:
        """Returns (user, created). created=False means it already existed."""
        existing = db.query(User).filter(User.username == username).first()
        if existing:
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
        db.flush()
        return user, True

    @staticmethod
    def get_or_create_child(
        db: Session,
        *,
        display_name: str,
        family_id: int,
        pin: str | None = None,
        avatar_color: str = "#FF6B6B",
    ) -> tuple[User, bool]:
        """Child accounts have role='child', no username, optional PIN."""
        existing = (
            db.query(User)
            .filter(User.family_id == family_id, User.display_name == display_name, User.role == "child")
            .first()
        )
        if existing:
            return existing, False
        child = User(
            id=next_id(),
            family_id=family_id,
            username=None,
            display_name=display_name,
            password_hash=None,
            role="child",
            avatar_color=avatar_color,
            pin_hash=_hash(pin) if pin else None,
        )
        db.add(child)
        db.flush()
        return child, True
