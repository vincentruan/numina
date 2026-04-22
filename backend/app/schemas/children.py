import re

from pydantic import BaseModel, field_validator

from app.constants.pin import ALLOWED_EMOJIS
from app.schemas.base import SnowflakeBase

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class CreateChildRequest(BaseModel):
    username: str  # 新增：必填，全局唯一
    display_name: str
    avatar_color: str = "#4F46E5"
    pin: list[str]  # 4 emojis

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("用户名长度至少3位")
        if len(v) > 50:
            raise ValueError("用户名长度不能超过50位")
        if not re.match(r"^[a-zA-Z0-9]+$", v):
            raise ValueError("用户名只能包含字母和数字")
        return v.lower()

    @field_validator("pin")
    @classmethod
    def check_pin(cls, v):
        if len(v) != 4:
            raise ValueError("PIN必须包含4个表情符号")
        for e in v:
            if e not in ALLOWED_EMOJIS:
                raise ValueError(f"无效的表情符号: {e}")
        return v

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v):
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("avatar_color必须是有效的十六进制颜色（如 #4F46E5）")
        return v

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v):
        if not v or not v.strip():
            raise ValueError("昵称不能为空")
        if len(v) > 50:
            raise ValueError("昵称不能超过50个字符")
        return v.strip()


class UpdateChildRequest(BaseModel):
    username: str | None = None  # 新增：允许修改 username
    display_name: str | None = None
    avatar_color: str | None = None
    pin: list[str] | None = None  # if provided, reset PIN

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError("用户名长度至少3位")
        if len(v) > 50:
            raise ValueError("用户名长度不能超过50位")
        if not re.match(r"^[a-zA-Z0-9]+$", v):
            raise ValueError("用户名只能包含字母和数字")
        return v.lower()

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v):
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("avatar_color必须是有效的十六进制颜色（如 #4F46E5）")
        return v

    @field_validator("pin")
    @classmethod
    def check_pin(cls, v):
        if v is None:
            return v
        if len(v) != 4:
            raise ValueError("PIN必须包含4个表情符号")
        for e in v:
            if e not in ALLOWED_EMOJIS:
                raise ValueError(f"无效的表情符号: {e}")
        return v


class ChildResponse(SnowflakeBase):
    id: int
    username: str  # 新增：必填
    display_name: str
    avatar_color: str
    is_active: bool


class ChildBindTokenResponse(BaseModel):
    token: str
    expires_at: str  # ISO format
    bind_url: str  # shareable URL
