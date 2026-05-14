# backend/tests/test_reminders.py


def test_get_reminder_summary_empty(client, auth_headers):
    resp = client.get("/api/v1/reminders/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0


def test_list_reminders_empty(client, auth_headers):
    resp = client.get("/api/v1/reminders", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_notification_config_default(client, auth_headers):
    resp = client.get("/api/v1/notification-config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["large_purchase_threshold_fixed"] is None


def test_update_notification_config(client, auth_headers):
    resp = client.put(
        "/api/v1/notification-config",
        headers=auth_headers,
        json={
            "large_purchase_threshold_fixed": 5000.0,
            "large_purchase_threshold_multiplier": 2.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["large_purchase_threshold_fixed"] == 5000.0


def test_dismiss_reminder(client, auth_headers, db):
    from apps.backend.app.models.reminder import Reminder
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    user = db.query(User).first()
    r = Reminder(
        id=next_id(),
        family_id=user.family_id,
        reminder_type="maturity",
        title="测试到期",
        body="测试内容",
        severity="warning",
    )
    db.add(r)
    db.commit()

    resp = client.patch(f"/api/v1/reminders/{r.id}/dismiss", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "dismissed"
