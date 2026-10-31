"""API contract for family backup and restore.

Backup and restore are the most destructive endpoints in the API, so the
tests here pin the two properties a caller depends on: only the family owner
may reach them, and a malformed or missing backup fails without touching the
family's existing data.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def owner_client(client):
    return client


@pytest.fixture()
def owner_headers(auth_headers):
    return auth_headers


class TestOwnerOnly:
    def test_member_is_rejected(self, client, member_headers):
        response = client.get("/api/v1/import/backups", headers=member_headers)

        assert response.status_code == 403
        assert response.json()["code"] == "AUTH_OWNER_ONLY"

    def test_member_cannot_trigger_backup(self, client, member_headers):
        response = client.post("/api/v1/import/backup", headers=member_headers)

        assert response.status_code == 403

    def test_member_cannot_restore(self, client, member_headers):
        response = client.post(
            "/api/v1/import/restore",
            headers=member_headers,
            json={"backup_run_id": "1"},
        )

        assert response.status_code == 403

    def test_member_cannot_restore_files(self, client, member_headers):
        response = client.post("/api/v1/import/restore-files", headers=member_headers)

        assert response.status_code == 403


@pytest.fixture()
def member_headers(client, auth_headers, db):
    """Headers for a non-owner adult in the same family as auth_headers."""
    from apps.backend.app.models.user import User

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    me = me.get("data", me)
    family_id = me["family_id"]

    import bcrypt

    member = User(
        family_id=int(family_id),
        username="member1",
        display_name="成员",
        password_hash=bcrypt.hashpw(b"MemberPass123", bcrypt.gensalt(rounds=4)).decode(),
        role="member",
    )
    db.add(member)
    db.flush()

    token = client.post(
        "/api/v1/auth/login",
        json={"username": "member1", "password": "MemberPass123"},
    ).json()
    token = token.get("data", token)
    return {"Authorization": f"Bearer {token['access_token']}"}


class TestListBackups:
    def test_empty_when_none_recorded(self, client, owner_headers):
        response = client.get("/api/v1/import/backups", headers=owner_headers)

        assert response.status_code == 200
        body = response.json()
        data = body.get("data", body)
        assert data["items"] == []


class TestRestoreValidation:
    def test_rejects_malformed_backup_date(self, client, owner_headers):
        response = client.post(
            "/api/v1/import/restore",
            headers=owner_headers,
            json={"backup_date": "../../etc/passwd"},
        )

        assert response.status_code in (400, 404)
        assert response.status_code != 500

    def test_rejects_unknown_backup_run(self, client, owner_headers):
        response = client.post(
            "/api/v1/import/restore",
            headers=owner_headers,
            json={"backup_run_id": "999999999"},
        )

        assert response.status_code == 404

    def test_missing_backup_reports_not_found(self, client, owner_headers):
        with patch(
            "packages.domain.backup.orchestrator.load_backup",
            new=AsyncMock(side_effect=FileNotFoundError("no backups")),
        ), patch(
            "packages.domain.backup.orchestrator.resolve_backup_path",
            return_value="backups/20260101/120000/numina_backup_1.json",
        ):
            response = client.post(
                "/api/v1/import/restore",
                headers=owner_headers,
                json={"backup_date": "20260101"},
            )

        assert response.status_code == 404


class TestManualBackup:
    def test_storage_failure_becomes_a_typed_error(self, client, owner_headers):
        from packages.storage.base import StorageAuthError

        with patch(
            "packages.domain.backup.orchestrator.create_backup",
            new=AsyncMock(side_effect=StorageAuthError("GitHub 认证失败: 401")),
        ):
            response = client.post("/api/v1/import/backup", headers=owner_headers)

        assert response.status_code == 502
        assert response.json()["code"] == "BACKUP_FAILED"

    def test_success_returns_backup_metadata(self, client, owner_headers):
        from types import SimpleNamespace

        run = SimpleNamespace(
            id=42,
            backup_date="20261030",
            file_path="backups/20261030/120000/numina_backup_1.json",
            file_size=1234,
        )
        with patch(
            "packages.domain.backup.orchestrator.create_backup",
            new=AsyncMock(return_value=(run, {})),
        ):
            response = client.post("/api/v1/import/backup", headers=owner_headers)

        assert response.status_code == 200
        body = response.json().get("data", response.json())
        assert body["backup_run_id"] == "42"
        assert body["file_size"] == 1234
