# backend/app/schemas/notification_config.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationConfigUpdate(BaseModel):
    large_purchase_threshold_fixed: float | None = None
    large_purchase_threshold_multiplier: float | None = None


class NotificationConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    large_purchase_threshold_fixed: float | None
    large_purchase_threshold_multiplier: float | None
    updated_at: datetime
