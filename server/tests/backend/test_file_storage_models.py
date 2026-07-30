"""Tests for file storage DB models."""
import pytest
from sqlalchemy.exc import IntegrityError

from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.models.sync_event import SyncEvent


def _make_backend(db, id="github-main", backend_type="github", is_default=False):
    backend = StorageBackend(
        id=id,
        backend_type=backend_type,
        display_name="Test GitHub",
        config='{"token": "encrypted"}',
        is_default=is_default,
        is_active=True,
    )
    db.add(backend)
    db.commit()
    db.refresh(backend)
    return backend


def _make_cached_file(db, family_id, user_id, sha256="abc123"):
    cf = CachedFile(
        family_id=family_id,
        user_id=user_id,
        sha256=sha256,
        local_path=f"/data/uploads/images/20260410/{sha256}.jpg",
        original_filename="photo.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        date_dir="20260410",
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return cf


def _register_user_and_get_ids(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "storageuser",
        "display_name": "Storage User",
        "password": "TestPass123",
        "family_name": "Storage Family",
        "family_invitation_code": "AUTO-STORAGE"
    })
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_data = me.json()["data"]
    return user_data["id"], user_data["family_id"]


class TestStorageBackendModel:
    def test_create_and_query(self, db):
        _backend = _make_backend(db, id="local-main", backend_type="local", is_default=True)
        fetched = db.query(StorageBackend).filter_by(id="local-main").first()
        assert fetched is not None
        assert fetched.backend_type == "local"
        assert fetched.is_default is True
        assert fetched.is_active is True

    def test_created_at_auto_set(self, db):
        backend = _make_backend(db)
        assert backend.created_at is not None


class TestCachedFileModel:
    def test_create_and_query(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id)
        fetched = db.query(CachedFile).filter_by(id=cf.id).first()
        assert fetched is not None
        assert fetched.sha256 == "abc123"
        assert fetched.date_dir == "20260410"
        assert fetched.deleted_at is None

    def test_sha256_family_unique_constraint(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        _make_cached_file(db, family_id=family_id, user_id=user_id, sha256="deadbeef")
        with pytest.raises(IntegrityError):
            _make_cached_file(db, family_id=family_id, user_id=user_id, sha256="deadbeef")

    def test_same_sha256_different_families_allowed(self, client, db):
        # Register first user
        user_id1, family_id1 = _register_user_and_get_ids(client)

        # Register second user in different family
        resp2 = client.post("/api/v1/auth/register", json={
            "username": "storageuser2",
            "display_name": "Storage User 2",
            "password": "TestPass456",
            "family_name": "Storage Family 2",
            "family_invitation_code": "AUTO-STORAGE-2"
        })
        assert resp2.status_code == 200
        token2 = resp2.json()["data"]["access_token"]
        me2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"})
        user_id2 = me2.json()["data"]["id"]
        family_id2 = me2.json()["data"]["family_id"]

        # Same sha256, different families — should not raise
        cf1 = _make_cached_file(db, family_id=family_id1, user_id=user_id1, sha256="shared_hash")
        cf2 = _make_cached_file(db, family_id=family_id2, user_id=user_id2, sha256="shared_hash")
        assert cf1.id != cf2.id


class TestFileRemoteLocationModel:
    def test_create_and_query(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id)

        loc = FileRemoteLocation(
            file_id=cf.id,
            backend_id=backend.id,
            remote_path="images/20260410/photo.jpg",
            sync_status="pending",
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)

        fetched = db.query(FileRemoteLocation).filter_by(id=loc.id).first()
        assert fetched is not None
        assert fetched.sync_status == "pending"
        assert fetched.retry_count == 0

    def test_unique_file_backend_constraint(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id)

        db.add(FileRemoteLocation(file_id=cf.id, backend_id=backend.id, sync_status="pending"))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(FileRemoteLocation(file_id=cf.id, backend_id=backend.id, sync_status="synced"))
            db.commit()

    def test_sync_status_transition(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id)

        loc = FileRemoteLocation(file_id=cf.id, backend_id=backend.id, sync_status="pending")
        db.add(loc)
        db.commit()

        loc.sync_status = "synced"
        db.commit()
        db.refresh(loc)
        assert loc.sync_status == "synced"


class TestSyncEventModel:
    def test_create_and_query(self, client, db):
        user_id, family_id = _register_user_and_get_ids(client)
        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id)

        event = SyncEvent(
            file_id=cf.id,
            backend_id=backend.id,
            event_type="upload_succeeded",
            detail='{"remote_path": "images/20260410/photo.jpg"}',
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        fetched = db.query(SyncEvent).filter_by(id=event.id).first()
        assert fetched is not None
        assert fetched.event_type == "upload_succeeded"
        assert fetched.occurred_at is not None
