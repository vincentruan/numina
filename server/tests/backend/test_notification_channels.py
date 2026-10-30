# backend/tests/test_notification_channels.py


def test_create_telegram_channel(client, auth_headers):
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "家庭群",
            "config": {"bot_token": "fake_token", "chat_id": "123456"},
            "is_enabled": True,
            "subscriptions": ["maturity", "expiring_soon"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["channel_type"] == "telegram"
    assert set(data["subscriptions"]) == {"maturity", "expiring_soon"}


def test_list_channels(client, auth_headers):
    client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "email",
            "name": "邮件通知",
            "config": {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "u",
                "smtp_password": "p",
                "smtp_from": "from@example.com",
                "to": "to@example.com",
            },
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
        },
    )
    resp = client.get("/api/v1/notification-channels", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


def test_update_channel(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "旧名称",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = create_resp.json()["data"]["id"]
    resp = client.put(
        f"/api/v1/notification-channels/{channel_id}",
        headers=auth_headers,
        json={"name": "新名称", "is_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "新名称"
    assert resp.json()["data"]["is_enabled"] is False


def test_delete_channel(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "待删除",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = create_resp.json()["data"]["id"]
    resp = client.delete(
        f"/api/v1/notification-channels/{channel_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    list_resp = client.get("/api/v1/notification-channels", headers=auth_headers)
    ids = [c["id"] for c in list_resp.json()["data"]]
    assert channel_id not in ids


def test_response_masks_sensitive_config(client, auth_headers):
    """Sensitive fields must be masked in the response, never echoed back."""
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Masked",
            "config": {"bot_token": "super_secret_token", "chat_id": "12345"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    # Bot token must be masked — never returned in plaintext.
    assert data["config"]["bot_token"] == "••••••••"
    # Non-sensitive values are returned as-is.
    assert data["config"]["chat_id"] == "12345"


def test_update_preserves_masked_secrets(client, auth_headers, db):
    """Echoing back the mask keeps the existing ciphertext unchanged.

    Asserts on the stored ciphertext, not the response: the response is masked
    unconditionally, so a response-only assertion would still pass if the
    preservation guard were removed.
    """
    from packages.db.models.notification_channel_config import (
        NotificationChannelConfig,
    )

    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Preserve",
            "config": {"bot_token": "original", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = int(create_resp.json()["data"]["id"])

    def stored_bot_token_plaintext() -> str | None:
        row = (
            db.query(NotificationChannelConfig)
            .filter_by(channel_id=channel_id, key="bot_token")
            .first()
        )
        if row is None:
            return None
        from packages.storage.config_crypto import decrypt_config

        decrypted = decrypt_config(row.value_encrypted)
        return decrypted.get("bot_token") if decrypted else None

    assert stored_bot_token_plaintext() == "original"

    # Frontend sends back the mask for bot_token and a new chat_id.
    resp = client.put(
        f"/api/v1/notification-channels/{channel_id}",
        headers=auth_headers,
        json={
            "config": {"bot_token": "••••••••", "chat_id": "2"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["config"]["chat_id"] == "2"
    # The real secret survived: the mask was not re-encrypted over it.
    assert stored_bot_token_plaintext() == "original"

    # A genuine new value still replaces the stored secret.
    resp = client.put(
        f"/api/v1/notification-channels/{channel_id}",
        headers=auth_headers,
        json={"config": {"bot_token": "rotated", "chat_id": "2"}},
    )
    assert resp.status_code == 200
    assert stored_bot_token_plaintext() == "rotated"


def test_delete_cleans_up_configs(client, auth_headers, db):
    """Deleting a channel must also remove its encrypted config rows."""
    from packages.db.models.notification_channel_config import (
        NotificationChannelConfig,
    )
    from packages.db.models.notification_subscription import NotificationSubscription

    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "email",
            "name": "ToDelete",
            "config": {"smtp_password": "s3cret", "to": "a@b.com"},
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
        },
    )
    channel_id = int(create_resp.json()["data"]["id"])
    assert (
        db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).count()
        == 2
    )

    resp = client.delete(
        f"/api/v1/notification-channels/{channel_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Both related row sets are gone; the channel row itself is gone too.
    assert (
        db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).count()
        == 0
    )
    assert (
        db.query(NotificationSubscription).filter_by(channel_id=channel_id).count() == 0
    )


def test_feature_status_endpoint(client, auth_headers):
    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "large_purchase" in data
    lp = data["large_purchase"]
    # No threshold or channels yet → all false/zero.
    assert lp["threshold_configured"] is False
    assert lp["subscribing_channel_count"] == 0
    assert lp["subscribing_channel_names"] == []


def test_feature_status_reflects_threshold_and_subscriptions(client, auth_headers):
    # Configure a threshold.
    client.put(
        "/api/v1/notification-config",
        headers=auth_headers,
        json={"large_purchase_threshold_fixed": 5000},
    )
    # Create a channel that subscribes to large_purchase.
    client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "LP Subscriber",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
        },
    )
    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    data = resp.json()["data"]["large_purchase"]
    assert data["threshold_configured"] is True
    assert data["subscribing_channel_count"] == 1
    assert "LP Subscriber" in data["subscribing_channel_names"]


def test_delivery_history_empty(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "History",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = create_resp.json()["data"]["id"]
    resp = client.get(
        f"/api/v1/notification-channels/{channel_id}/delivery-history",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_webpush_channel_crud(client, auth_headers):
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "webpush",
            "name": "Browser Push",
            "config": {},
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["channel_type"] == "webpush"
    assert "large_purchase" in data["subscriptions"]


def test_event_availability_defaults(client, auth_headers):
    """With no special assets, expiring_soon/maturity are no_data."""
    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    avail = {e["event_type"]: e["status"] for e in data["event_availability"]}
    assert avail["expiring_soon"] == "no_data"
    assert avail["maturity"] == "no_data"
    assert avail["large_purchase"] == "needs_config"


def test_event_availability_with_expiry_asset(client, auth_headers, db):
    """An asset with warranty_expiry_date makes expiring_soon ready."""
    from datetime import date, timedelta

    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category
    from apps.backend.app.utils.snowflake import next_id

    # Get the auth'd user's family_id via /me endpoint
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]
    family_id = int(me["family_id"])
    user_id = int(me["id"])

    category = db.query(Category).first()
    asset = Asset(
        id=next_id(),
        family_id=family_id,
        user_id=user_id,
        category_id=category.id,
        name="Expiring Asset",
        asset_type="physical",
        is_archived=False,
        warranty_expiry_date=date.today() + timedelta(days=30),
    )
    db.add(asset)
    db.commit()

    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    data = resp.json()["data"]
    avail = {e["event_type"]: e["status"] for e in data["event_availability"]}
    assert avail["expiring_soon"] == "ready"


def test_event_availability_ignores_expired_dates(client, auth_headers, db):
    """A past expiry date can never fire, so the badge must not say ready."""
    from datetime import date, timedelta

    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category
    from apps.backend.app.utils.snowflake import next_id

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]
    category = db.query(Category).first()
    db.add(
        Asset(
            id=next_id(),
            family_id=int(me["family_id"]),
            user_id=int(me["id"]),
            category_id=category.id,
            name="Expired Warranty",
            asset_type="physical",
            is_archived=False,
            warranty_expiry_date=date.today() - timedelta(days=10),
        )
    )
    db.commit()

    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    avail = {e["event_type"]: e["status"] for e in resp.json()["data"]["event_availability"]}
    assert avail["expiring_soon"] == "no_data"


def test_event_availability_large_purchase_needs_both_halves(client, auth_headers):
    """Threshold alone is not enough; dispatch also needs a subscribed channel."""
    client.put(
        "/api/v1/notification-config",
        headers=auth_headers,
        json={"large_purchase_threshold_fixed": 5000},
    )

    def status_of() -> str:
        resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
        avail = {
            e["event_type"]: e["status"]
            for e in resp.json()["data"]["event_availability"]
        }
        return avail["large_purchase"]

    assert status_of() == "needs_config"

    # Adding a subscribed, enabled channel completes the other half.
    client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "LP Subscriber",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
        },
    )
    assert status_of() == "ready"


def test_digest_time_rejects_malformed_value(client, auth_headers):
    """A malformed digest_time would silently never fire, so the API rejects it."""
    for bad in ("8:00", "25:00", "21:60", "abc", ""):
        resp = client.post(
            "/api/v1/notification-channels",
            headers=auth_headers,
            json={
                "channel_type": "telegram",
                "name": "Bad Time",
                "config": {"bot_token": "t", "chat_id": "1"},
                "is_enabled": True,
                "subscriptions": [],
                "digest_mode": "daily",
                "digest_time": bad,
            },
        )
        assert resp.status_code == 422, bad

    # A well-formed time is accepted.
    ok = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Good Time",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
            "digest_mode": "daily",
            "digest_time": "08:30",
        },
    )
    assert ok.status_code == 201
    assert ok.json()["data"]["digest_time"] == "08:30"


def test_event_availability_covers_every_registry_event(client, auth_headers):
    """Every registry event must carry a badge entry; a missing one renders blank."""
    from apps.backend.app.services.notification.registry import NOTIFICATION_CATEGORIES

    registry_types = {
        t for cat in NOTIFICATION_CATEGORIES.values() for t in cat["events"]
    }
    resp = client.get("/api/v1/notification-config/status", headers=auth_headers)
    returned = {e["event_type"] for e in resp.json()["data"]["event_availability"]}
    assert registry_types == returned


def test_email_digest_pinned_to_immediate(client, auth_headers):
    """email cannot deliver digests, so the stored mode must not be 'daily'."""
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "email",
            "name": "Mail",
            "config": {"smtp_host": "smtp.example.com", "to": "a@b.com"},
            "is_enabled": True,
            "subscriptions": [],
            "digest_mode": "daily",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["digest_mode"] == "immediate"


def test_update_pins_email_and_webpush_digest_to_immediate(client, auth_headers):
    """email / webpush cannot deliver digests — the PUT path must pin them too.

    The create path already pins; without the same guard on update a client can
    flip an existing email channel to 'daily', which makes the digest job skip
    it while immediate dispatch is also skipped, so it never delivers at all.
    """
    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "email",
            "name": "Mail",
            "config": {"smtp_host": "smtp.example.com", "to": "a@b.com"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    email_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["digest_mode"] == "immediate"

    resp = client.put(
        f"/api/v1/notification-channels/{email_id}",
        headers=auth_headers,
        json={"digest_mode": "daily", "digest_time": "08:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["digest_mode"] == "immediate"
    # The time is still stored: it is meaningless for an immediate channel but
    # dropping it would silently lose a user's setting if the type ever gains
    # digest support.
    assert resp.json()["data"]["digest_time"] == "08:00"

    # A channel type that *can* digest keeps what the user asked for.
    tg = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "TG",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    tg_id = tg.json()["data"]["id"]
    resp = client.put(
        f"/api/v1/notification-channels/{tg_id}",
        headers=auth_headers,
        json={"digest_mode": "daily", "digest_time": "08:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["digest_mode"] == "daily"

    # webpush goes through the same pin.
    wp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "webpush",
            "name": "Push",
            "config": {},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    wp_id = wp.json()["data"]["id"]
    resp = client.put(
        f"/api/v1/notification-channels/{wp_id}",
        headers=auth_headers,
        json={"digest_mode": "daily"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["digest_mode"] == "immediate"


def test_delivery_history_returns_records_newest_first(client, auth_headers, db):
    """The history query joins reminders, orders by time and honors limit."""
    from datetime import datetime

    from apps.backend.app.models.reminder import Reminder
    from apps.backend.app.utils.snowflake import next_id
    from packages.db.models.reminder_notification import ReminderNotification

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]
    family_id = int(me["family_id"])

    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "History",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = int(create_resp.json()["data"]["id"])

    # Snowflake ids are time-ordered, but created_at is what the endpoint sorts
    # by, so set it explicitly rather than relying on wall-clock ordering.
    times = [
        datetime(2026, 1, 1, 8, 0),
        datetime(2026, 1, 2, 8, 0),
        datetime(2026, 1, 3, 8, 0),
    ]
    for i, created_at in enumerate(times):
        reminder_id = next_id()
        db.add(
            Reminder(
                id=reminder_id,
                family_id=family_id,
                reminder_type="maturity",
                title=f"提醒 {i}",
                body="body",
                severity="info",
            )
        )
        db.add(
            ReminderNotification(
                id=next_id(),
                reminder_id=reminder_id,
                channel_id=channel_id,
                status="sent" if i != 1 else "failed",
                created_at=created_at,
            )
        )
    db.commit()

    resp = client.get(
        f"/api/v1/notification-channels/{channel_id}/delivery-history",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["reminder_title"] for r in rows] == ["提醒 2", "提醒 1", "提醒 0"]
    # The join must carry the reminder's type through, not the notification's.
    assert {r["reminder_type"] for r in rows} == {"maturity"}
    assert [r["status"] for r in rows] == ["sent", "failed", "sent"]
    # Snowflake ids are serialized as strings.
    assert all(isinstance(r["id"], str) and isinstance(r["reminder_id"], str) for r in rows)

    limited = client.get(
        f"/api/v1/notification-channels/{channel_id}/delivery-history",
        headers=auth_headers,
        params={"limit": 2},
    )
    assert [r["reminder_title"] for r in limited.json()["data"]] == ["提醒 2", "提醒 1"]

    # A limit outside the sane range is clamped, not rejected.
    clamped = client.get(
        f"/api/v1/notification-channels/{channel_id}/delivery-history",
        headers=auth_headers,
        params={"limit": 0},
    )
    assert clamped.status_code == 200
    assert len(clamped.json()["data"]) == 1


def test_delivery_history_only_lists_own_channel(client, auth_headers, second_user_headers):
    other = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Mine",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    ).json()["data"]

    resp = client.get(
        f"/api/v1/notification-channels/{other['id']}/delivery-history",
        headers=second_user_headers,
    )
    assert resp.status_code == 404
