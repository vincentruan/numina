"""Tests for GET /api/v1/admin/audit-logs endpoint (R8)."""

from datetime import datetime, timedelta

from apps.backend.app.models.security_audit_log import SecurityAuditLog
from apps.backend.app.utils.snowflake import next_id


def _seed_logs(db, family_id: int, count: int = 3) -> list[SecurityAuditLog]:
    """Seed audit log rows for the given family."""
    logs = []
    for i in range(count):
        log = SecurityAuditLog(
            id=next_id(),
            event_type="login_success" if i % 2 == 0 else "login_failed",
            user_id=family_id + i,  # distinct user_ids per row
            family_id=family_id,
            ip_address="127.0.0.1",
            outcome="success" if i % 2 == 0 else "failure",
            created_at=datetime.utcnow() - timedelta(minutes=i),
        )
        db.add(log)
        logs.append(log)
    db.commit()
    return logs


def _seed_logs_with_timestamps(db, family_id: int) -> list[SecurityAuditLog]:
    """Seed audit log rows at known timestamps for date-filter testing."""
    base = datetime(2025, 6, 15, 12, 0, 0)
    logs = []
    for i, offset_days in enumerate([0, 5, 10]):
        log = SecurityAuditLog(
            id=next_id(),
            event_type="login_success",
            user_id=family_id + i,
            family_id=family_id,
            ip_address="127.0.0.1",
            outcome="success",
            created_at=base + timedelta(days=offset_days),
        )
        db.add(log)
        logs.append(log)
    db.commit()
    return logs


class TestListAuditLogs:
    def test_owner_can_list(self, client, auth_headers, db):
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=3)

        resp = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page"] == 1
        assert body["page_size"] == 20

    def test_non_owner_gets_403(self, client, db):
        """A member (non-owner) must receive 403."""
        from apps.backend.app.models.family_invitation_code import FamilyInvitationCode

        db.add(FamilyInvitationCode(code="AUTO-AUDIT-MEMBER"))
        db.commit()

        # Register owner first
        owner_resp = client.post("/api/v1/auth/register", json={
            "username": "audit_owner",
            "display_name": "Audit Owner",
            "password": "TestPass123",
            "family_name": "Audit Family",
            "family_invitation_code": "AUTO-AUDIT-MEMBER",
        })
        assert owner_resp.status_code == 200

        # Get the family's invite_code (stored on Family model, used by join_family)
        owner_token = owner_resp.json()["data"]["access_token"]
        family_resp = client.get(
            "/api/v1/family",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        invite_code = family_resp.json()["data"]["invite_code"]

        # Join as a member (no FamilyInvitationCode needed — join_family uses Family.invite_code)
        member_resp = client.post("/api/v1/auth/family/join", json={
            "username": "audit_member",
            "display_name": "Audit Member",
            "password": "TestPass456",
            "invite_code": invite_code,
        })
        assert member_resp.status_code == 200
        member_token = member_resp.json()["data"]["access_token"]

        resp = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403

    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/admin/audit-logs")
        assert resp.status_code == 401

    def test_pagination(self, client, auth_headers, db):
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=5)

        resp = client.get(
            "/api/v1/admin/audit-logs?page=1&page_size=2",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 2

        # Second page
        resp2 = client.get(
            "/api/v1/admin/audit-logs?page=2&page_size=2",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body2 = resp2.json()["data"]
        assert len(body2["items"]) == 2

        # Third page — only 1 item left
        resp3 = client.get(
            "/api/v1/admin/audit-logs?page=3&page_size=2",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body3 = resp3.json()["data"]
        assert len(body3["items"]) == 1

    def test_filter_by_event_type(self, client, auth_headers, db):
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=4)  # 2 login_success, 2 login_failed

        resp = client.get(
            "/api/v1/admin/audit-logs?event_type=login_success",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 2
        assert all(item["event_type"] == "login_success" for item in body["items"])

    def test_tenant_isolation(self, client, auth_headers, second_user_headers, db):
        """Logs from another family must not appear in the response."""
        from apps.backend.app.models.user import User

        user1 = db.query(User).filter_by(username="testuser").first()
        user2 = db.query(User).filter_by(username="testuser2").first()

        _seed_logs(db, user1.family_id, count=2)
        _seed_logs(db, user2.family_id, count=3)

        resp = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.json()["data"]
        # Only user1's family logs
        assert body["total"] == 2
        assert all(item["family_id"] == str(user1.family_id) for item in body["items"])

    def test_user_id_serialized_as_string(self, client, auth_headers, db):
        """SnowflakeBase must serialize user_id as a string, not an integer."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=1)

        resp = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        item = resp.json()["data"]["items"][0]
        # SnowflakeBase serializes *_id fields as strings
        assert isinstance(item["user_id"], str)
        assert isinstance(item["family_id"], str)
        assert isinstance(item["id"], str)

    def test_ordered_newest_first(self, client, auth_headers, db):
        """Results must be ordered by created_at DESC."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=3)

        resp = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        items = resp.json()["data"]["items"]
        timestamps = [item["created_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_audit_log_filter_by_date_from(self, client, auth_headers, db):
        """Only entries created >= date_from are returned."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs_with_timestamps(db, user.family_id)  # day 0, 5, 10

        # Filter: only entries from day 5 onward
        resp = client.get(
            "/api/v1/admin/audit-logs?date_from=2025-06-20T00:00:00",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 2  # day 5 and day 10 entries

    def test_audit_log_filter_by_date_to(self, client, auth_headers, db):
        """Only entries created <= date_to are returned."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs_with_timestamps(db, user.family_id)  # day 0, 5, 10

        # Filter: only entries up to day 5
        resp = client.get(
            "/api/v1/admin/audit-logs?date_to=2025-06-20T12:00:00",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 2  # day 0 and day 5 entries

    def test_audit_log_filter_by_date_range(self, client, auth_headers, db):
        """Returns entries in [date_from, date_to] intersection."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs_with_timestamps(db, user.family_id)  # day 0, 5, 10

        # Filter: only entries between day 3 and day 7
        resp = client.get(
            "/api/v1/admin/audit-logs?date_from=2025-06-18T00:00:00&date_to=2025-06-22T23:59:59",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 1  # only day 5 entry
        assert body["items"][0]["user_id"] == str(user.family_id + 1)

    def test_audit_log_filter_by_user_id(self, client, auth_headers, db):
        """Only entries matching user_id are returned."""
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_logs(db, user.family_id, count=4)  # user_ids: family_id+0..+3

        target_user_id = user.family_id + 2
        resp = client.get(
            f"/api/v1/admin/audit-logs?user_id={target_user_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 1
        assert body["items"][0]["user_id"] == str(target_user_id)
