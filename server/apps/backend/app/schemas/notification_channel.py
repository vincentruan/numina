# backend/app/schemas/notification_channel.py
from datetime import datetime

from pydantic import BaseModel, Field

from apps.backend.app.schemas.base import SnowflakeBase

# The scheduler matches digest_time against a ±2 minute window; a value it
# cannot parse silently never fires, so reject malformed input at the boundary.
DIGEST_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class NotificationChannelCreate(BaseModel):
    channel_type: str  # telegram | email
    name: str
    config: dict  # 明文传输，服务层 JSON 序列化后加密存储
    is_enabled: bool = True
    subscriptions: list[str] = []  # reminder_type list
    digest_mode: str = "immediate"
    digest_time: str = Field(default="21:00", pattern=DIGEST_TIME_PATTERN)


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    subscriptions: list[str] | None = None
    digest_mode: str | None = None
    digest_time: str | None = Field(default=None, pattern=DIGEST_TIME_PATTERN)


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
    # Latest delivery outcome, joined from reminder_notifications.
    last_delivery_status: str | None = None
    last_delivery_at: datetime | None = None


class ChannelTestResult(BaseModel):
    success: bool
    error: str | None = None


class DeliveryRecord(SnowflakeBase):
    id: int
    reminder_id: int
    reminder_type: str
    reminder_title: str
    status: str
    created_at: datetime
