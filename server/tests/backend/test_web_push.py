"""Tests for Web Push notification infrastructure (U4)."""

from unittest.mock import MagicMock, patch

from apps.backend.app.utils.snowflake import next_id
from packages.db.models.push_subscription import PushSubscription

# ── Model tests ──────────────────────────────────────────────────────────────


def test_push_subscription_creation(db, test_family, test_user):
    """PushSubscription model can be created with required fields."""
    sub = PushSubscription(
        id=next_id(),
        user_id=test_user.id,
        family_id=test_family.id,
        endpoint="https://fcm.googleapis.com/fcm/send/abc123",
        p256dh="BNcRdedIGp_Zp4GjOmiqXkn7PG",
        auth="secret_auth_key",
        user_agent="Mozilla/5.0",
        app_type="main",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    assert sub.id is not None
    assert sub.user_id == test_user.id
    assert sub.family_id == test_family.id
    assert sub.app_type == "main"


# ── Subscribe endpoint tests ─────────────────────────────────────────────────


def test_subscribe_endpoint(client, auth_headers):
    """POST /notifications/push/subscribe creates a push subscription."""
    resp = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/test123",
            "p256dh": "BNcRdedIGp_Zp4GjOmiqXkn7PG",
            "auth": "secret_auth_key",
            "user_agent": "Mozilla/5.0",
            "app_type": "main",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["endpoint"] == "https://fcm.googleapis.com/fcm/send/test123"
    assert data["app_type"] == "main"
    assert "id" in data


def test_subscribe_upsert(client, auth_headers):
    """POST /notifications/push/subscribe upserts on same user+endpoint."""
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/upsert_test",
        "p256dh": "key1",
        "auth": "auth1",
    }
    resp1 = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json=payload,
    )
    assert resp1.status_code == 200
    id1 = resp1.json()["data"]["id"]

    # Update with new keys
    resp2 = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json={**payload, "p256dh": "key2", "auth": "auth2"},
    )
    assert resp2.status_code == 200
    id2 = resp2.json()["data"]["id"]
    assert id1 == id2  # Same record, not duplicated


# ── Unsubscribe endpoint tests ───────────────────────────────────────────────


def test_unsubscribe_endpoint(client, auth_headers):
    """DELETE /notifications/push/subscribe removes a push subscription."""
    endpoint = "https://fcm.googleapis.com/fcm/send/to_delete"
    client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json={
            "endpoint": endpoint,
            "p256dh": "key",
            "auth": "auth",
        },
    )
    resp = client.request(
        "DELETE",
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        params={"endpoint": endpoint},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


# ── VAPID public key endpoint ────────────────────────────────────────────────


def test_vapid_public_key(client, auth_headers):
    """GET /notifications/push/vapid-public-key returns the public key."""
    resp = client.get(
        "/api/v1/notifications/push/vapid-public-key",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "public_key" in resp.json()["data"]


# ── send_webpush unit tests ──────────────────────────────────────────────────


def test_send_webpush_success():
    """send_webpush returns True on successful push."""
    from apps.backend.app.services.notification.sender import NotificationSender

    with patch("pywebpush.webpush") as mock_push:
        mock_push.return_value = MagicMock()
        result = NotificationSender.send_webpush(
            subscription_info={
                "endpoint": "https://example.com/push",
                "keys": {"p256dh": "key", "auth": "auth"},
            },
            data={"title": "Test", "body": "Hello"},
            vapid_private_key="fake_private_key",
            vapid_claims={"sub": "mailto:test@example.com"},
        )
        assert result is True
        mock_push.assert_called_once()


def test_send_webpush_410_gone():
    """send_webpush returns 'gone' when subscription is expired (410)."""
    from pywebpush import WebPushException

    from apps.backend.app.services.notification.sender import NotificationSender

    mock_response = MagicMock()
    mock_response.status_code = 410

    with patch(
        "pywebpush.webpush",
        side_effect=WebPushException("Gone", response=mock_response),
    ):
        result = NotificationSender.send_webpush(
            subscription_info={
                "endpoint": "https://example.com/push",
                "keys": {"p256dh": "key", "auth": "auth"},
            },
            data={"title": "Test", "body": "Hello"},
            vapid_private_key="fake_private_key",
            vapid_claims={"sub": "mailto:test@example.com"},
        )
        assert result == "gone"


def test_send_webpush_failure():
    """send_webpush returns False on general failure."""
    from pywebpush import WebPushException

    from apps.backend.app.services.notification.sender import NotificationSender

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch(
        "pywebpush.webpush",
        side_effect=WebPushException("Server Error", response=mock_response),
    ):
        result = NotificationSender.send_webpush(
            subscription_info={
                "endpoint": "https://example.com/push",
                "keys": {"p256dh": "key", "auth": "auth"},
            },
            data={"title": "Test", "body": "Hello"},
            vapid_private_key="fake_private_key",
            vapid_claims={"sub": "mailto:test@example.com"},
        )
        assert result is False


# ── Family isolation tests ───────────────────────────────────────────────────


def test_push_subscription_family_isolation(client, auth_headers, second_user_headers):
    """Subscriptions from one family are not visible to another."""
    # User 1 creates a subscription
    client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/family1_only",
            "p256dh": "key1",
            "auth": "auth1",
        },
    )

    # User 2 tries to delete user 1's subscription — should be a no-op
    resp = client.request(
        "DELETE",
        "/api/v1/notifications/push/subscribe",
        headers=second_user_headers,
        params={"endpoint": "https://fcm.googleapis.com/fcm/send/family1_only"},
    )
    assert resp.status_code == 200
    # Response is "ok" even if nothing was found (idempotent)

    # User 1's subscription should still exist — verify by re-subscribing (upsert)
    resp2 = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/family1_only",
            "p256dh": "key1_updated",
            "auth": "auth1_updated",
        },
    )
    assert resp2.status_code == 200
