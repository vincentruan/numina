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
