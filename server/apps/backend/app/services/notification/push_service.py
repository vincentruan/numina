"""Direct push notification sending for non-reminder events (R12 family interactions).

These are real-time interaction notifications (child completed a task, wish
fulfilled, milestone earned) that bypass the reminder/dispatcher system because
they are not scheduled reminders.
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def send_family_interaction_push(
    db: Session,
    family_id: int,
    title: str,
    body: str,
    reminder_type: str = "family_interaction",
    navigate_to: str = "",
) -> None:
    """Send a push notification for family interaction events.

    Sends to ALL push subscriptions in the family (both main and child apps).
    Failures are silently ignored so they never block the caller's request.
    """
    try:
        from apps.backend.app.services.notification.sender import NotificationSender
        from packages.core.settings import settings
        from packages.db.models.push_subscription import PushSubscription

        if not settings.VAPID_PRIVATE_KEY:
            logger.debug("VAPID private key not configured, skipping push")
            return

        subscriptions = (
            db.query(PushSubscription)
            .filter(PushSubscription.family_id == family_id)
            .all()
        )
        if not subscriptions:
            return

        vapid_claims = {"sub": settings.VAPID_SUBJECT}

        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            }
            notification_data = {
                "title": title,
                "body": body,
                "reminder_type": reminder_type,
                "navigate_to": navigate_to,
            }
            result = NotificationSender.send_webpush(
                subscription_info,
                notification_data,
                settings.VAPID_PRIVATE_KEY,
                vapid_claims,
            )
            if result == "gone":
                db.delete(sub)

        db.commit()
    except Exception:
        logger.warning("Failed to send family interaction push", exc_info=True)
