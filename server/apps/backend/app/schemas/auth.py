import json
import re
from datetime import date as date_type
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.app.schemas.base import SnowflakeBase

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码长度至少8位")
    if len(password) > 128:
        raise ValueError("密码长度不能超过128位")
    if not re.search(r"[A-Z]", password):
        raise ValueError("密码必须包含大写字母")
    if not re.search(r"[a-z]", password):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含数字")
    return password


def validate_username(username: str) -> str:
    """Validate username format.

    - Length: 3-50 characters
    - Auto-converts to lowercase for easy memorization
    - Allowed: lowercase letters, digits, underscore, hyphen, dot
    """
    username = username.lower()
    if len(username) < 3:
        raise ValueError("用户名长度至少3位")
    if len(username) > 50:
        raise ValueError("用户名长度不能超过50位")
    if not re.match(r"^[a-z0-9_.\-]+$", username):
        raise ValueError("用户名只能包含小写字母、数字、下划线、中划线和点号")
    return username


# ---------------------------------------------------------------------------
# Username change history helpers
# ---------------------------------------------------------------------------

_MAX_USERNAME_CHANGES = 3
_USERNAME_CHANGE_WINDOW_DAYS = 30


def parse_username_change_history(history_raw: str | None) -> list[datetime]:
    """Parse ``username_change_history`` JSON into recent change datetimes (within the window)."""
    if not history_raw:
        return []
    try:
        raw_list: list[str] = json.loads(history_raw)
    except (json.JSONDecodeError, TypeError):
        return []
    cutoff = datetime.utcnow() - timedelta(days=_USERNAME_CHANGE_WINDOW_DAYS)
    return [
        datetime.fromisoformat(ts)
        for ts in raw_list
        if datetime.fromisoformat(ts) > cutoff
    ]


def compute_username_change_info(history_raw: str | None) -> tuple[int, str | None]:
    """Compute remaining username changes and the next-available ISO timestamp.

    Returns:
        ``(remaining, next_available_at)`` — *next_available_at* is ``None``
        when there is no recent history.
    """
    recent = parse_username_change_history(history_raw)
    remaining = max(0, _MAX_USERNAME_CHANGES - len(recent))
    next_available: str | None = None
    if recent:
        next_available = (
            min(recent) + timedelta(days=_USERNAME_CHANGE_WINDOW_DAYS)
        ).isoformat()
    return remaining, next_available


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    family_name: str
    family_invitation_code: str
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("family_invitation_code")
    @classmethod
    def normalize_invitation_code(cls, v: str) -> str:
        """Normalize to uppercase for consistent matching."""
        v = v.upper().strip()
        if len(v) < 4 or len(v) > 6:
            raise ValueError("邀请码长度必须在4-6位之间")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class JoinFamilyRequest(BaseModel):
    username: str
    password: str
    display_name: str
    invite_code: str
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResponse(SnowflakeBase):
    id: int
    family_id: int
    username: str | None  # NULL for child accounts
    display_name: str
    avatar_color: str
    avatar_url: str | None = None
    role: str
    is_active: bool
    theme: str = "light"
    language: str = "zh-CN"
    default_currency: str = "CNY"
    theme_color: str | None = None
    view_mode: str = "card"
    second_factor_enabled: bool = False
    second_factor_type: str | None = None
    birthday: date_type | None = None
    birthday_is_lunar: bool = False
    username_changes_remaining: int = 3
    username_next_available_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def compute_username_change_fields(cls, data):  # type: ignore[no-untyped-def]
        # Extract username_change_history from ORM object or dict
        if isinstance(data, dict):
            history_raw = data.get("username_change_history")
        else:
            history_raw = getattr(data, "username_change_history", None)

        remaining, next_available = compute_username_change_info(history_raw)

        # Convert ORM object to dict so extra computed fields are included
        if not isinstance(data, dict):
            data = {
                c.name: getattr(data, c.name, None)
                for c in data.__table__.columns  # type: ignore[attr-defined]
            }
        data["username_changes_remaining"] = remaining
        data["username_next_available_at"] = next_available
        return data

    @field_validator("avatar_color", mode="before")
    @classmethod
    def sanitize_avatar_color(cls, v: str | None) -> str:
        if v is None or not _HEX_COLOR_RE.match(v):
            return "#4F46E5"
        return v


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_color: str | None = None
    avatar_url: str | None = None

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("avatar_color必须是有效的十六进制颜色（如 #4F46E5）")
        return v

    @field_validator("avatar_url")
    @classmethod
    def check_avatar_url(cls, v: str | None) -> str | None:
        """Validate avatar_url: allow null, /uploads/..., /icons/3d/..., or single emoji."""
        if v is None:
            return v
        # Reject path traversal attempts
        if ".." in v:
            raise ValueError("avatar_url 不允许包含路径遍历序列")
        # Allow uploaded images
        if v.startswith("/uploads/"):
            return v
        # Allow 3D icon paths (originals and thumbnails)
        if v.startswith("/icons/3d/") or v.startswith("/icons/3d-thumbs/"):
            return v
        # Allow single emoji (max 8 bytes, no HTML metacharacters)
        if len(v.encode("utf-8")) <= 8 and not any(c in v for c in "<>&\"'"):
            return v
        raise ValueError("avatar_url 必须是有效的上传路径、图标路径或单个表情符号")


class UpdateSettingsRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    default_currency: str | None = None
    view_mode: str | None = None
    theme_color: str | None = None

    @field_validator("theme_color")
    @classmethod
    def check_theme_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("theme_color必须是有效的十六进制颜色（如 #007aff）")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangeUsernameRequest(BaseModel):
    new_username: str

    @field_validator("new_username")
    @classmethod
    def check_new_username(cls, v: str) -> str:
        return validate_username(v)


class ResetPasswordRequest(BaseModel):
    """Reset password via notification channel — no old password required."""
    pass


# ---------------------------------------------------------------------------
# Child authentication schemas
# ---------------------------------------------------------------------------



class VerifyParentRequest(BaseModel):
    password: str  # Parent's password to verify adult identity on shared device


class VerifyParentPasswordRequest(BaseModel):
    password: str


class ChildRefreshResponse(BaseModel):
    message: str = "token refreshed"


# ---------------------------------------------------------------------------
# Two-step login schemas
# ---------------------------------------------------------------------------


class LoginStep1Request(BaseModel):
    username: str
    password: str
    altcha: str | None = None

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)


class LoginStep1Response(SnowflakeBase):
    temp_token: str | None = None          # present when second_factor_required=True
    second_factor_required: bool
    second_factor_type: str | None = None  # 'numeric_pin' | 'emoji_pin' | 'totp'
    # present when second_factor_required=False (direct login)
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    # user info for UI display (always present)
    user_id: int | None = None
    display_name: str | None = None
    avatar_color: str | None = None
    avatar_url: str | None = None


class LoginStep2Request(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    temp_token: str
    factor_type: str   # 'numeric_pin' | 'emoji_pin'
    payload: dict      # e.g. {"pin": "1234"} or {"pin_sequence": ["🐱", ...]}


# ---------------------------------------------------------------------------
# PIN management schemas
# ---------------------------------------------------------------------------


class SetupNumericPinRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def check_pin(cls, v: str) -> str:
        from apps.backend.app.constants.pin import (
            NUMERIC_PIN_MAX_LENGTH,
            NUMERIC_PIN_MIN_LENGTH,
        )
        if not v.isdigit():
            raise ValueError("数字PIN只能包含数字")
        if len(v) < NUMERIC_PIN_MIN_LENGTH or len(v) > NUMERIC_PIN_MAX_LENGTH:
            raise ValueError(f"数字PIN长度必须在{NUMERIC_PIN_MIN_LENGTH}-{NUMERIC_PIN_MAX_LENGTH}位之间")
        return v


class ChangeNumericPinRequest(BaseModel):
    old_pin: str
    new_pin: str

    @field_validator("new_pin")
    @classmethod
    def check_new_pin(cls, v: str) -> str:
        from apps.backend.app.constants.pin import (
            NUMERIC_PIN_MAX_LENGTH,
            NUMERIC_PIN_MIN_LENGTH,
        )
        if not v.isdigit():
            raise ValueError("数字PIN只能包含数字")
        if len(v) < NUMERIC_PIN_MIN_LENGTH or len(v) > NUMERIC_PIN_MAX_LENGTH:
            raise ValueError(f"数字PIN长度必须在{NUMERIC_PIN_MIN_LENGTH}-{NUMERIC_PIN_MAX_LENGTH}位之间")
        return v


class SetChildPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UpdateMemberInfoRequest(BaseModel):
    display_name: str | None = Field(None, max_length=20)
    avatar_color: str | None = None
    avatar_url: str | None = None
    birthday: date_type | None = None
    birthday_is_lunar: bool | None = None

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("avatar_color必须是有效的十六进制颜色（如 #4F46E5）")
        return v

    @field_validator("avatar_url")
    @classmethod
    def check_avatar_url(cls, v: str | None) -> str | None:
        """Validate avatar_url: allow null, /uploads/..., /icons/3d/..., or single emoji."""
        if v is None:
            return v
        # Reject path traversal attempts
        if ".." in v:
            raise ValueError("avatar_url 不允许包含路径遍历序列")
        # Allow uploaded images
        if v.startswith("/uploads/"):
            return v
        # Allow 3D icon paths (originals and thumbnails)
        if v.startswith("/icons/3d/") or v.startswith("/icons/3d-thumbs/"):
            return v
        # Allow single emoji (max 8 bytes, no HTML metacharacters)
        if len(v.encode("utf-8")) <= 8 and not any(c in v for c in "<>&\"'"):
            return v
        raise ValueError("avatar_url 必须是有效的上传路径、图标路径或单个表情符号")
