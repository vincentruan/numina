# backend/app/schemas/notification_channel.py
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import SnowflakeBase


class NotificationChannelCreate(BaseModel):
    channel_type: str  # telegram | email
    name: str
    config: dict  # 明文传输，服务层 JSON 序列化后加密存储
    is_enabled: bool = True
    subscriptions: list[str] = []  # reminder_type list


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    subscriptions: list[str] | None = None


class NotificationChannelResponse(SnowflakeBase):
    id: int
    family_id: int
    channel_type: str
    name: str
    is_enabled: bool
    subscriptions: list[str] = []
    created_at: datetime
    updated_at: datetime
