"""Tests for the family-scoped storage backend router."""
import pytest

from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.services.storage.config_crypto import decrypt_config, encrypt_config
from apps.backend.app.services.storage.factory import reset_instances


def _register_owner(client, invite_code="AUT01"):
    resp = client.post("/api/v1/auth/register", json={
        "username": "storageowner",
        "display_name": "Storage Owner",
        "password": "TestPass123",
        "family_name": "Storage Family",
        "family_invitation_code": invite_code,
    })
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    return data["access_token"]


def _register_member(client, invite_code):
    resp = client.post("/api/v1/auth/family/join", json={
        "username": "storagemember2",
        "display_name": "Storage Member",
        "password": "TestPass123",
        "invite_code": invite_code,
        "altcha": "bypass-test",
    })
    print("MEMBER RESP:", resp.status_code, resp.text)
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    return data["access_token"]


class TestStorageBackendEndpoints:
    def test_get_status_not_configured(self, client, db):
        token = _register_owner(client)
        resp = client.get("/api/v1/family/storage/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"configured": False, "backend_type": None, "display_name": None, "is_active": False}

    def test_get_backend_not_configured_returns_null(self, client, db):
        token = _register_owner(client)
        resp = client.get("/api/v1/family/storage", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_create_backend_success(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
            "display_name": "My GitHub Backup",
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["backend_type"] == "github"
        assert data["display_name"] == "My GitHub Backup"
        assert data["is_active"] is True
        assert "config" not in data

    def test_create_backend_already_exists(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        resp1 = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "STORAGE_BACKEND_ALREADY_EXISTS"

    def test_create_backend_member_forbidden(self, client, db):
        owner_token = _register_owner(client, "AUT01")
        family_resp = client.get("/api/v1/family", headers={"Authorization": f"Bearer {owner_token}"})
        invite_code = family_resp.json()["data"]["invite_code"]
        member_token = _register_member(client, invite_code)

        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {member_token}"})
        assert resp.status_code == 403

    def test_create_backend_mismatched_config_type(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "base_url": "https://example.com/dav",
                "username": "u",
                "password": "p",
            },
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422

    def test_update_backend_success(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        create_resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        backend_id = create_resp.json()["data"]["id"]

        update_payload = {
            "display_name": "Updated Name",
            "is_active": False,
        }
        resp = client.patch(f"/api/v1/family/storage/{backend_id}", json=update_payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["display_name"] == "Updated Name"
        assert data["is_active"] is False

    def test_update_backend_not_found(self, client, db):
        token = _register_owner(client)
        resp = client.patch("/api/v1/family/storage/999999", json={"display_name": "x"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_backend_success(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        create_resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        backend_id = create_resp.json()["data"]["id"]

        resp = client.delete(f"/api/v1/family/storage/{backend_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

        # Verify backend is gone
        get_resp = client.get("/api/v1/family/storage", headers={"Authorization": f"Bearer {token}"})
        assert get_resp.json()["data"] is None

    def test_delete_backend_orphans_remote_locations(self, client, db):
        from apps.backend.app.models.cached_file import CachedFile

        token = _register_owner(client)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        family_id = me.json()["data"]["family_id"]
        user_id = me.json()["data"]["id"]

        # Create backend
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        create_resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        backend_id = create_resp.json()["data"]["id"]

        # Create a cached file and remote location manually
        cf = CachedFile(
            family_id=family_id,
            user_id=user_id,
            sha256="testhash",
            local_path="/tmp/test.jpg",
            original_filename="test.jpg",
            mime_type="image/jpeg",
            size_bytes=100,
            date_dir="20260410",
        )
        db.add(cf)
        db.flush()
        loc = FileRemoteLocation(
            file_id=cf.id,
            backend_id=backend_id,
            sync_status="synced",
            remote_path="20260410/test.jpg",
            remote_url="http://example.com/20260410/test.jpg",
        )
        db.add(loc)
        db.commit()

        resp = client.delete(f"/api/v1/family/storage/{backend_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

        # Verify location is orphaned
        db.refresh(loc)
        assert loc.backend_id is None
        assert loc.sync_status == "orphaned"

    def test_config_encrypted_before_storage(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "github",
            "config": {
                "repo_owner": "testowner",
                "repo_name": "testrepo",
                "branch": "main",
                "token": "ghp_testtoken",
            },
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        backend_id = resp.json()["data"]["id"]

        backend = db.query(StorageBackend).filter_by(id=backend_id).first()
        decrypted = decrypt_config(backend.config)
        assert decrypted["token"] == "ghp_testtoken"
        assert decrypted["repo_owner"] == "testowner"


class TestWebDAVBackend:
    def test_create_webdav_backend_success(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "webdav",
            "config": {
                "base_url": "https://example.com/dav",
                "username": "user",
                "password": "pass",
            },
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["backend_type"] == "webdav"

    def test_create_webdav_backend_invalid_url(self, client, db):
        token = _register_owner(client)
        payload = {
            "backend_type": "webdav",
            "config": {
                "base_url": "ftp://example.com/dav",
                "username": "user",
                "password": "pass",
            },
        }
        resp = client.post("/api/v1/family/storage", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422


@pytest.fixture(autouse=True)
def _reset_factory_instances():
    reset_instances()
    yield
    reset_instances()
