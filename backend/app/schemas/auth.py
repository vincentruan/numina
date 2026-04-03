import re

from pydantic import BaseModel, field_validator


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码长度至少8位")
    if not re.search(r"[A-Z]", password):
        raise ValueError("密码必须包含大写字母")
    if not re.search(r"[a-z]", password):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含数字")
    return password


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    family_name: str
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    username: str
    password: str
    altcha: str | None = None  # Captcha payload (required in production)


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

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResponse(BaseModel):
    id: str
    family_id: str
    username: str
    display_name: str
    avatar_color: str
    role: str
    is_active: bool
    theme: str = "light"
    language: str = "zh-CN"
    default_currency: str = "CNY"
    view_mode: str = "card"

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_color: str | None = None


class UpdateSettingsRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    default_currency: str | None = None
    view_mode: str | None = None
