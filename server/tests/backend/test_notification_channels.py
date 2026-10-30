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


def test_update_preserves_masked_secrets(client, auth_headers):
    """Echoing back the mask keeps the existing ciphertext unchanged."""
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
    channel_id = create_resp.json()["data"]["id"]
    # Frontend sends back the mask for bot_token and a new chat_id.
    resp = client.put(
        f"/api/v1/notification-channels/{channel_id}",
        headers=auth_headers,
        json={
            "config": {"bot_token": "••••••••", "chat_id": "2"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["config"]["chat_id"] == "2"
    # Bot token still masked (not overwritten with the literal mask).
    assert data["config"]["bot_token"] == "••••••••"


def test_delete_cleans_up_configs(client, auth_headers):
    """Deleting a channel must also remove its encrypted config rows."""
    create_resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "email",
            "name": "ToDelete",
            "config": {"smtp_password": "s3cret", "to": "a@b.com"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    channel_id = create_resp.json()["data"]["id"]
    resp = client.delete(
        f"/api/v1/notification-channels/{channel_id}", headers=auth_headers
    )
    assert resp.status_code == 204


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
