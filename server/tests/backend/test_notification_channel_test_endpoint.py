"""HTTP-level tests for POST /notification-channels/{id}/test.

The sender branches are already covered at the service level
(test_notification_channel_test_send.py). What is only reachable through the
route — family scoping, result shaping, and the fact that a test send leaves no
delivery rows behind — is covered here.
"""

from unittest.mock import AsyncMock, patch

import pytest

_SEND_TELEGRAM = (
    "apps.backend.app.services.notification.dispatcher.NotificationSender.send_telegram"
)


@pytest.fixture
def telegram_channel(client, auth_headers):
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "TG",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": ["maturity"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def test_test_endpoint_reports_success(client, auth_headers, telegram_channel):
    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=True)):
        resp = client.post(
            f"/api/v1/notification-channels/{telegram_channel['id']}/test",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"success": True, "error": None}


def test_test_endpoint_reports_failure_reason(client, auth_headers, telegram_channel):
    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=False)):
        resp = client.post(
            f"/api/v1/notification-channels/{telegram_channel['id']}/test",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is False
    assert data["error"]


def test_test_endpoint_uses_stored_config(client, auth_headers, telegram_channel):
    """The route must decrypt the stored rows, not expect config in the request."""
    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=True)) as send:
        client.post(
            f"/api/v1/notification-channels/{telegram_channel['id']}/test",
            headers=auth_headers,
        )
    assert send.await_args.kwargs["bot_token"] == "t"
    assert send.await_args.kwargs["chat_id"] == "1"


def test_test_endpoint_writes_no_delivery_rows(
    client, auth_headers, telegram_channel, db
):
    """A test send is not a delivery: retry counters and digest bookkeeping
    must not move because the user clicked 'test'."""
    from packages.db.models.reminder_notification import ReminderNotification

    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=True)):
        client.post(
            f"/api/v1/notification-channels/{telegram_channel['id']}/test",
            headers=auth_headers,
        )
    assert (
        db.query(ReminderNotification)
        .filter_by(channel_id=int(telegram_channel["id"]))
        .count()
        == 0
    )


def test_test_endpoint_is_family_scoped(
    client, auth_headers, second_user_headers, telegram_channel
):
    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=True)) as send:
        resp = client.post(
            f"/api/v1/notification-channels/{telegram_channel['id']}/test",
            headers=second_user_headers,
        )
    assert resp.status_code == 404
    send.assert_not_awaited()


def test_test_endpoint_missing_channel(client, auth_headers):
    with patch(_SEND_TELEGRAM, new=AsyncMock(return_value=True)):
        resp = client.post(
            "/api/v1/notification-channels/99999999999999/test",
            headers=auth_headers,
        )
    assert resp.status_code == 404


def test_test_endpoint_requires_auth(client, auth_headers, telegram_channel):
    # The shared client keeps the register/login cookies, so an "anonymous"
    # request from the same client would still authenticate. Drop them first.
    client.cookies.clear()
    resp = client.post(f"/api/v1/notification-channels/{telegram_channel['id']}/test")
    assert resp.status_code in (401, 403)
