import re

from pydantic import BaseModel, field_validator

from app.constants.pin import ALLOWED_EMOJIS

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


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
    - Allowed: letters, digits, underscore, hyphen, @ (email format)
    """
    if len(username) < 3:
        raise ValueError("用户名长度至少3位")
    if len(username) > 50:
        raise ValueError("用户名长度不能超过50位")
    # Allow letters, digits, underscore, hyphen, and @ (for email-like usernames)
    if not re.match(r"^[a-zA-Z0-9_\-@]+$", username):
        raise ValueError("用户名只能包含字母、数字、下划线、中划线和@符号")
    return username


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    family_name: str
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


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


class UserResponse(BaseModel):
    id: str
    family_id: str
    username: str | None  # NULL for child accounts
    display_name: str
    avatar_color: str
    role: str
    is_active: bool
    theme: str = "light"
    language: str = "zh-CN"
    default_currency: str = "CNY"
    view_mode: str = "card"

    model_config = {"from_attributes": True}

    @field_validator("avatar_color", mode="before")
    @classmethod
    def sanitize_avatar_color(cls, v: str | None) -> str:
        if v is None or not _HEX_COLOR_RE.match(v):
            return "#4F46E5"
        return v


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_color: str | None = None

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("avatar_color必须是有效的十六进制颜色（如 #4F46E5）")
        return v


class UpdateSettingsRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    default_currency: str | None = None
    view_mode: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


# ---------------------------------------------------------------------------
# Child authentication schemas
# ---------------------------------------------------------------------------


class ChildPinLoginRequest(BaseModel):
    child_id: str  # User UUID
    pin_sequence: list[str]  # 4 emojis from ALLOWED_EMOJIS

    @field_validator("pin_sequence")
    @classmethod
    def validate_pin_sequence(cls, v: list[str]) -> list[str]:
        if len(v) != 4:
            raise ValueError("PIN 必须是 4 个表情")
        for emoji in v:
            if emoji not in ALLOWED_EMOJIS:
                raise ValueError(f"无效的表情: {emoji}")
        return v


class VerifyParentRequest(BaseModel):
    password: str  # Parent's password to verify adult identity on shared device


class VerifyParentPasswordRequest(BaseModel):
    password: str


class ChildRefreshResponse(BaseModel):
    message: str = "token refreshed"
