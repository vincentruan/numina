"""Digest-mode routing in the dispatcher.

``digest_mode='daily'`` channels are delivered by scheduler_worker's
``notification_digest_job`` at the user's configured time. The dispatcher must
therefore skip them — otherwise the digest arrives immediately (making the
setting a no-op) and the digest job later finds nothing pending and sends
nothing (making the digest itself always empty).

These tests pin both halves: immediate dispatch skips daily channels, and the
retry sweep does not treat a daily channel as an outstanding delivery.

Additionally the digest must only include reminders whose type the channel is
actually subscribed to. Since daily channels now get no immediate delivery at
all, a digest that ignored subscriptions would surface reminders for types the
user never asked the channel to receive.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.backend.app.models.reminder import Reminder
from apps.backend.app.services.notification import dispatcher
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.notification_channel import NotificationChannel
from packages.db.models.notification_subscription import NotificationSubscription
from packages.db.models.reminder_notification import ReminderNotification

_SEND_EMAIL = "apps.backend.app.services.notification.sender.NotificationSender.send_email"
_RENDER = "apps.backend.app.services.notification.dispatcher.render_template"

_TEMPLATE_VARS = {
    "asset_name": "理财产品 A",
    "maturity_date": "2026-11-01",
    "days_left": 2,
    "amount": "10000.00",
}


@pytest.fixture
def family_id(client, auth_headers):
    return int(client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]["family_id"])


def _make_channel(
    db, family_id: int, *, digest_mode: str, name: str, channel_type: str = "email"
) -> NotificationChannel:
    channel = NotificationChannel(
        id=next_id(),
        family_id=family_id,
        channel_type=channel_type,
        name=name,
        is_enabled=True,
        digest_mode=digest_mode,
        digest_time="21:00",
    )
    db.add(channel)
    db.flush()
    return channel


def _make_reminder(
    db, family_id: int, *, reminder_type: str = "maturity"
) -> Reminder:
    reminder = Reminder(
        id=next_id(),
        family_id=family_id,
        reminder_type=reminder_type,
        title=f"{reminder_type} title",
        body="body",
        severity="info",
    )
    db.add(reminder)
    db.commit()
    return reminder


def test_immediate_dispatch_skips_daily_channels(db, family_id):
    immediate = _make_channel(db, family_id, digest_mode="immediate", name="now")
    daily = _make_channel(db, family_id, digest_mode="daily", name="digest")
    for channel in (immediate, daily):
        db.add(
            NotificationSubscription(
                id=next_id(), channel_id=channel.id, reminder_type="maturity"
            )
        )
    db.commit()
    reminder = _make_reminder(db, family_id)

    send = MagicMock(return_value=True)
    with patch(_SEND_EMAIL, new=send):
        dispatcher._dispatch_notifications(db, reminder, _TEMPLATE_VARS)

    notified = {
        rn.channel_id
        for rn in db.query(ReminderNotification).filter_by(reminder_id=reminder.id).all()
    }
    assert notified == {immediate.id}
    assert daily.id not in notified
    assert send.call_count == 1


def test_immediate_dispatch_does_not_skip_unknown_modes(db, family_id):
    """Filtering is ``!= 'daily'`` so a stray value still delivers nominally.

    An allow-list of ``== 'immediate'`` would silently drop every channel whose
    stored mode is anything else, including values written by older versions.
    """
    stray = _make_channel(db, family_id, digest_mode="weekly", name="stray")
    db.add(
        NotificationSubscription(
            id=next_id(), channel_id=stray.id, reminder_type="maturity"
        )
    )
    db.commit()
    reminder = _make_reminder(db, family_id)

    with patch(_SEND_EMAIL, new=MagicMock(return_value=True)):
        dispatcher._dispatch_notifications(db, reminder, _TEMPLATE_VARS)

    assert (
        db.query(ReminderNotification).filter_by(channel_id=stray.id).count() == 1
    )


def test_retry_sweep_ignores_daily_channels(db, family_id):
    """A daily channel is not "still pending" — the digest job owns it.

    Without this, every retry sweep re-enters dispatch for a family whose only
    channel is a digest channel, on every reminder run, forever.
    """
    daily = _make_channel(db, family_id, digest_mode="daily", name="digest")
    db.add(
        NotificationSubscription(
            id=next_id(), channel_id=daily.id, reminder_type="maturity"
        )
    )
    db.commit()
    _make_reminder(db, family_id)

    send = MagicMock(return_value=True)
    with patch(_SEND_EMAIL, new=send), patch(_RENDER, return_value=""):
        dispatcher._retry_failed_notifications(db)

    assert (
        db.query(ReminderNotification).filter_by(channel_id=daily.id).count() == 0
    )
    assert send.call_count == 0


def test_retry_sweep_still_retries_immediate_channels(db, family_id):
    immediate = _make_channel(db, family_id, digest_mode="immediate", name="now")
    db.add(
        NotificationSubscription(
            id=next_id(), channel_id=immediate.id, reminder_type="maturity"
        )
    )
    db.commit()
    _make_reminder(db, family_id)

    with patch(_SEND_EMAIL, new=MagicMock(return_value=True)), patch(
        _RENDER, return_value=""
    ):
        dispatcher._retry_failed_notifications(db)

    assert (
        db.query(ReminderNotification).filter_by(channel_id=immediate.id).count() == 1
    )


def test_digest_only_includes_subscribed_types(db, family_id):
    """A channel subscribed to maturity must not receive chore reminders."""
    channel = _make_channel(
        db, family_id, digest_mode="daily", name="digest", channel_type="telegram"
    )
    db.add(
        NotificationSubscription(
            id=next_id(), channel_id=channel.id, reminder_type="maturity"
        )
    )
    db.commit()

    maturity = _make_reminder(db, family_id, reminder_type="maturity")
    _make_reminder(db, family_id, reminder_type="chore_completed")

    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_telegram",
        new=AsyncMock(return_value=True),
    ):
        asyncio.run(dispatcher._dispatch_digest(db, channel))

    notified = {rn.reminder_id for rn in db.query(ReminderNotification).all()}
    assert notified == {maturity.id}


def test_digest_with_no_subscriptions_does_not_send(db, family_id):
    channel = _make_channel(
        db, family_id, digest_mode="daily", name="digest", channel_type="telegram"
    )
    db.commit()
    _make_reminder(db, family_id, reminder_type="maturity")

    send = AsyncMock(return_value=True)
    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_telegram",
        new=send,
    ):
        asyncio.run(dispatcher._dispatch_digest(db, channel))

    send.assert_not_awaited()
    assert db.query(ReminderNotification).count() == 0
