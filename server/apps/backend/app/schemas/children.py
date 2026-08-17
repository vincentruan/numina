import re

from pydantic import BaseModel, field_validator

from apps.backend.app.constants.pin import ALLOWED_EMOJIS
from apps.backend.app.schemas.base import SnowflakeBase

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class CreateChildRequest(BaseModel):
    username: str  # 必填，全局唯一
    display_name: str
    password: str  # 初始密码，由父母代设
    avatar_color: str = "#4F46E5"
    pin: list[str]  # 4 emojis

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("用户名长度至少3位")
        if len(v) > 50:
            raise ValueError("用户名长度不能超过50位")
        if not re.match(r"^[a-z0-9_.\-]+$", v.lower()):
            raise ValueError("用户名只能包含小写字母、数字、下划线、中划线和点号")
        return v.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        from apps.backend.app.schemas.auth import validate_password_strength
        return validate_password_strength(v)

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
    avatar_url: str | None = None
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
        if not re.match(r"^[a-z0-9_.\-]+$", v.lower()):
            raise ValueError("用户名只能包含小写字母、数字、下划线、中划线和点号")
        return v.lower()

    @field_validator("avatar_color")
    @classmethod
    def check_avatar_color(cls, v):
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
        # Allow 3D icon paths
        if v.startswith("/icons/3d/"):
            return v
        # Allow single emoji (max 8 bytes, no HTML metacharacters)
        if len(v.encode("utf-8")) <= 8 and not any(c in v for c in "<>&\"'"):
            return v
        raise ValueError("avatar_url 必须是有效的上传路径、图标路径或单个表情符号")

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
    username: str
    display_name: str
    avatar_color: str
    avatar_url: str | None = None
    is_active: bool
