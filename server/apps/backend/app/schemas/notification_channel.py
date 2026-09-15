# backend/app/schemas/notification_channel.py
from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class NotificationChannelCreate(BaseModel):
    channel_type: str  # telegram | email
    name: str
    config: dict  # 明文传输，服务层 JSON 序列化后加密存储
    is_enabled: bool = True
    subscriptions: list[str] = []  # reminder_type list
    digest_mode: str = "immediate"
    digest_time: str = "21:00"


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    subscriptions: list[str] | None = None
    digest_mode: str | None = None
    digest_time: str | None = None


class NotificationChannelResponse(SnowflakeBase):
    id: int
    family_id: int
    channel_type: str
    name: str
    is_enabled: bool
    config: dict = {}
    subscriptions: list[str] = []
    digest_mode: str = "immediate"
    digest_time: str = "21:00"
    created_at: datetime
    updated_at: datetime
