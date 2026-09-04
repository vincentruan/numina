"""Second factor verification strategies.

Supports numeric PIN (adults) and emoji PIN (children).
TOTP is reserved for future implementation.
"""

import time
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Protocol

import bcrypt
from sqlalchemy.orm import Session

from apps.backend.app.models.user import User

_LOCKOUT_MINUTES = 15
_MAX_ATTEMPTS = 3


class SecondFactorStrategy(Protocol):
    factor_type: str

    def is_configured(self, user: User) -> bool: ...
    def verify(self, db: Session, user: User, payload: dict) -> bool: ...


# In-memory failure tracking: {user_id: (fail_count, first_fail_time)}
_numeric_pin_attempts: dict[int, tuple[int, float]] = {}
_emoji_pin_attempts: dict[int, tuple[int, float]] = {}


def _record_failure(
    db: Session,
    user: User,
    attempts: dict[int, tuple[int, float]],
    fail_count_attr: str,
    locked_until_attr: str,
) -> None:
    user_id = user.id
    now = time.time()
    count, first_time = attempts.get(user_id, (0, now))

    if now - first_time > _LOCKOUT_MINUTES * 60:
        count, first_time = 0, now

    count += 1
    attempts[user_id] = (count, first_time)
    setattr(user, fail_count_attr, count)
    db.commit()

    if count >= _MAX_ATTEMPTS:
        setattr(
            user,
            locked_until_attr,
            datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES),
        )
        db.commit()
        del attempts[user_id]


def _check_lockout(user: User, locked_until_attr: str) -> datetime | None:
    locked_until: datetime | None = getattr(user, locked_until_attr)
    if locked_until is not None and locked_until > datetime.now(UTC):
        return locked_until
    return None


def _clear_lockout(
    db: Session,
    user: User,
    attempts: dict[int, tuple[int, float]],
    fail_count_attr: str,
    locked_until_attr: str,
) -> None:
    setattr(user, locked_until_attr, None)
    setattr(user, fail_count_attr, 0)
    attempts.pop(user.id, None)
    db.commit()


class NumericPinStrategy:
    factor_type = "numeric_pin"

    def is_configured(self, user: User) -> bool:
        return user.numeric_pin_hash is not None

    def verify(self, db: Session, user: User, payload: dict) -> bool:
        from apps.backend.app.errors import AppError, ErrorCode

        pin: str = payload.get("pin", "")

        if not self.is_configured(user):
            return False

        locked_until = _check_lockout(user, "numeric_pin_locked_until")
        if locked_until:
            raise AppError(
                ErrorCode.AUTH_PIN_LOCKED,
                details={"locked_until": locked_until.isoformat()},
            )

        pin_hash = user.numeric_pin_hash
        if pin_hash is None:
            return False

        if not bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8")):
            _record_failure(
                db, user, _numeric_pin_attempts,
                "numeric_pin_fail_count", "numeric_pin_locked_until",
            )
            return False

        _clear_lockout(db, user, _numeric_pin_attempts, "numeric_pin_fail_count", "numeric_pin_locked_until")
        return True


class EmojiPinStrategy:
    factor_type = "emoji_pin"

    def is_configured(self, user: User) -> bool:
        return user.pin_hash is not None

    def verify(self, db: Session, user: User, payload: dict) -> bool:
        from apps.backend.app.errors import AppError, ErrorCode

        pin_sequence: list[str] = payload.get("pin_sequence", [])

        if not self.is_configured(user):
            return False

        locked_until = _check_lockout(user, "pin_locked_until")
        if locked_until:
            raise AppError(
                ErrorCode.AUTH_PIN_LOCKED,
                details={"locked_until": locked_until.isoformat()},
            )

        pin_hash = user.pin_hash
        if pin_hash is None:
            return False

        normalized = unicodedata.normalize("NFC", "".join(pin_sequence))
        if not bcrypt.checkpw(normalized.encode("utf-8"), pin_hash.encode("utf-8")):
            _record_failure(
                db, user, _emoji_pin_attempts,
                "pin_fail_count", "pin_locked_until",
            )
            return False

        _clear_lockout(db, user, _emoji_pin_attempts, "pin_fail_count", "pin_locked_until")
        return True


class TotpStrategy:
    factor_type = "totp"

    def is_configured(self, user: User) -> bool:
        return False

    def verify(self, db: Session, user: User, payload: dict) -> bool:
        raise NotImplementedError("TOTP 尚未实现")


_STRATEGIES: dict[str, SecondFactorStrategy] = {
    "numeric_pin": NumericPinStrategy(),
    "emoji_pin": EmojiPinStrategy(),
    "totp": TotpStrategy(),
}


def get_strategy(factor_type: str) -> SecondFactorStrategy:
    strategy = _STRATEGIES.get(factor_type)
    if strategy is None:
        from apps.backend.app.errors import AppError, ErrorCode
        raise AppError(ErrorCode.VALIDATION_ERROR, details={"factor_type": f"不支持的验证类型: {factor_type}"})
    return strategy
