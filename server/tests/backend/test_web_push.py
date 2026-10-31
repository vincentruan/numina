"""Tests for Web Push notification infrastructure (U4)."""

from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.utils.snowflake import next_id
from packages.db.models.push_subscription import PushSubscription
from tests.backend.conftest import child_login_two_phase

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


# ── Child subscription endpoint tests ──────────────────────────────────────

CHILD_PASSWORD = "ChildPass1"
CHILD_PIN = ["🐱", "🌟", "🎈", "🐶"]


@pytest.fixture
def child_user_and_headers(client, auth_headers):
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "pushchild",
            "password": CHILD_PASSWORD,
            "display_name": "Push Child",
            "avatar_color": "#FF5733",
            "pin": CHILD_PIN,
        },
    )
    assert resp.status_code == 201, resp.text
    token = child_login_two_phase(client, "pushchild", CHILD_PASSWORD, CHILD_PIN)
    return {"Authorization": f"Bearer {token}"}


def test_child_can_subscribe_and_is_forced_to_child_app_type(client, child_user_and_headers):
    """Child sessions may subscribe, but the server forces app_type='child'.

    If a child client submitted app_type='main', it would end up on the
    parent-scoped subscription list and receive adult-oriented push — a
    privacy regression we must never allow.
    """
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/child_test",
        "p256dh": "child_key",
        "auth": "child_auth",
        "app_type": "main",  # client asks for main
    }
    resp = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=child_user_and_headers,
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["app_type"] == "child"  # server-enforced


def test_child_subscribe_unknown_app_type_still_forced_to_child(client, child_user_and_headers):
    """Unknown app_type from a child is also forced to 'child'."""
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/child_unknown",
        "p256dh": "k", "auth": "a",
        "app_type": "desktop",  # not in {main, child}
    }
    resp = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=child_user_and_headers,
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["app_type"] == "child"


def test_adult_subscribe_preserves_main_when_explicit(client, auth_headers):
    """Adults with app_type='main' get 'main' — no unintended downgrade."""
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/adult_main_test",
        "p256dh": "k", "auth": "a",
        "app_type": "main",
    }
    resp = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=auth_headers,
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["app_type"] == "main"


def test_family_interaction_push_excludes_child_subscriptions(db, test_family, test_user):
    """send_family_interaction_push must NOT notify child devices.

    Regression guard for the app_type='main' filter at push_service.py:44.
    If that filter is removed, child subscriptions (which share the same
    family_id) would receive parent-oriented push like "X completed a chore".
    """
    from apps.backend.app.services.notification.push_service import (
        send_family_interaction_push,
    )

    # Seed one main-app subscription (parent) and one child-app subscription.
    main_sub = PushSubscription(
        id=next_id(),
        user_id=test_user.id,
        family_id=test_family.id,
        endpoint="https://fcm.googleapis.com/fcm/send/parent_endpoint",
        p256dh="parent_key",
        auth="parent_auth",
        app_type="main",
    )
    child_sub = PushSubscription(
        id=next_id(),
        user_id=test_user.id,
        family_id=test_family.id,
        endpoint="https://fcm.googleapis.com/fcm/send/child_endpoint",
        p256dh="child_key",
        auth="child_auth",
        app_type="child",
    )
    db.add(main_sub)
    db.add(child_sub)
    db.commit()

    notified_endpoints: list[str] = []

    def fake_send(subscription_info, notification_data, vapid_private_key, vapid_claims):
        notified_endpoints.append(subscription_info["endpoint"])
        return "sent"

    with patch(
        "apps.backend.app.services.notification.sender.NotificationSender.send_webpush",
        side_effect=fake_send,
    ), patch(
        "packages.core.settings.settings"
    ) as mock_settings:
        mock_settings.VAPID_PRIVATE_KEY = "test-key"
        mock_settings.VAPID_SUBJECT = "test-subject"
        send_family_interaction_push(
            db, test_family.id, "Test", "Body"
        )

    assert "https://fcm.googleapis.com/fcm/send/parent_endpoint" in notified_endpoints
    assert "https://fcm.googleapis.com/fcm/send/child_endpoint" not in notified_endpoints
