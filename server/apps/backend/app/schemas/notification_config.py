# backend/app/schemas/notification_config.py
from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class NotificationConfigUpdate(BaseModel):
    large_purchase_threshold_fixed: float | None = None
    large_purchase_threshold_multiplier: float | None = None


class NotificationConfigResponse(SnowflakeBase):
    id: int
    family_id: int
    large_purchase_threshold_fixed: float | None
    large_purchase_threshold_multiplier: float | None
    updated_at: datetime


class LargePurchaseStatus(SnowflakeBase):
    """Cross-references the threshold config with event subscriptions.

    Used by the frontend to warn when only one half of the
    large-purchase feature is configured.
    """

    threshold_configured: bool
    subscribing_channel_count: int
    # Names of channels that subscribe to ``large_purchase`` so the threshold
    # page can link the user straight to them.
    subscribing_channel_names: list[str] = []


class NotificationFeatureStatus(SnowflakeBase):
    large_purchase: LargePurchaseStatus
