"""Tests for background sync job and file management API."""
import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.cached_file import CachedFile
from app.models.file_remote_location import FileRemoteLocation
from app.models.storage_backend import StorageBackend as StorageBackendModel
from app.services.storage.base import StorageConnectionError


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _register_and_get_ids(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "syncuser",
        "display_name": "Sync User",
        "password": "TestPass123",
        "family_name": "Sync Family",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    data = me.json()
    return data["id"], data["family_id"], token


def _make_cached_file(db, family_id, user_id, local_path="/tmp/test.jpg"):
    cf = CachedFile(
        family_id=family_id,
        user_id=user_id,
        sha256="testhash123",
        local_path=local_path,
        original_filename="test.jpg",
        mime_type="image/jpeg",
        size_bytes=100,
        date_dir="20260410",
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return cf


def _make_backend(db, is_default=True):
    backend = StorageBackendModel(
        id="webdav-test",
        backend_type="webdav",
        display_name="Test WebDAV",
        config='{"url": "http://localhost", "username": "user", "password": "pass"}',
        is_default=is_default,
        is_active=True,
    )
    db.add(backend)
    db.commit()
    db.refresh(backend)
    return backend


def _make_location(db, file_id, backend_id, sync_status="pending", retry_count=0):
    loc = FileRemoteLocation(
        file_id=file_id,
        backend_id=backend_id,
        sync_status=sync_status,
        retry_count=retry_count,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


# ── Sync job tests ────────────────────────────────────────────────────────────

class TestFileSyncJob:
    def test_sync_job_processes_pending_row(self, db, tmp_path):
        """Sync job calls backend.save() and updates sync_status to synced."""
        from app.scheduler import file_sync_job

        # Write a real temp file
        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"fake-image-data")

        user_id, family_id = "user-1", "family-1"
        # Insert family/user stubs directly — use existing db fixture
        # Instead, use a real registered user via the db fixture
        # We'll patch SessionLocal to return our test db
        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id="fam-sync", user_id="usr-sync", local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="pending")

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(return_value="20260410/test.jpg")
        mock_backend.get_url = MagicMock(return_value="http://localhost/20260410/test.jpg")

        loc_id = loc.id  # capture before session is closed by job

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend):
            run(file_sync_job())

        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.sync_status == "synced"
        assert loc_updated.remote_path == "20260410/test.jpg"
        mock_backend.save.assert_called_once()
    def test_sync_job_marks_failed_on_storage_error(self, db, tmp_path):
        """Sync job increments retry_count on StorageError; marks failed after 3 attempts."""
        from app.scheduler import file_sync_job

        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id="fam-err", user_id="usr-err", local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="pending")

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(side_effect=StorageConnectionError("connection refused"))

        loc_id = loc.id  # capture before session is closed by job

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend):
            run(file_sync_job())

        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.sync_status == "pending"  # still retryable after first failure
        assert loc_updated.retry_count == 1
        assert "connection refused" in (loc_updated.last_error or "")

    def test_sync_job_marks_failed_after_max_retries(self, db, tmp_path):
        """Sync job marks status=failed when retry_count reaches 3."""
        from app.scheduler import file_sync_job

        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id="fam-max2", user_id="usr-max2", local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="pending", retry_count=2)

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(side_effect=StorageConnectionError("still down"))

        loc_id = loc.id

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend):
            run(file_sync_job())

        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.sync_status == "failed"
        assert loc_updated.retry_count == 3

    def test_sync_job_skips_rows_with_max_retries(self, db, tmp_path):
        """Rows with retry_count >= 3 are skipped."""
        from app.scheduler import file_sync_job

        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id="fam-max", user_id="usr-max", local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="pending", retry_count=3)

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(return_value="path")

        loc_id = loc.id  # capture before session is closed by job

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend):
            run(file_sync_job())

        mock_backend.save.assert_not_called()
        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.sync_status == "pending"  # unchanged

    def test_sync_job_no_default_backend_does_nothing(self, db):
        """If no default backend, sync job exits early."""
        from app.scheduler import file_sync_job

        with patch("app.scheduler.SessionLocal", return_value=db):
            run(file_sync_job())  # Should not raise


# ── File management API tests ─────────────────────────────────────────────────

class TestDeleteFileEndpoint:
    def test_delete_file_soft_deletes(self, client, db, tmp_path):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        local_file = tmp_path / "photo.jpg"
        local_file.write_bytes(b"data")

        cf = _make_cached_file(db, family_id=family_id, user_id=user_id, local_path=str(local_file))

        with patch("app.routers.files.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            resp = client.delete(f"/api/v1/files/{cf.id}", headers=headers)
        assert resp.status_code == 204

        db.refresh(cf)
        assert cf.deleted_at is not None

    def test_delete_file_removes_local_file(self, client, db, tmp_path):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        local_file = tmp_path / "photo.jpg"
        local_file.write_bytes(b"data")

        cf = _make_cached_file(db, family_id=family_id, user_id=user_id, local_path=str(local_file))

        with patch("app.routers.files.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            client.delete(f"/api/v1/files/{cf.id}", headers=headers)
        assert not local_file.exists()

    def test_delete_file_not_found(self, client, db):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.delete("/api/v1/files/nonexistent-id", headers=headers)
        assert resp.status_code == 404

    def test_delete_file_requires_auth(self, client, db):
        resp = client.delete("/api/v1/files/some-id")
        assert resp.status_code == 401

    def test_delete_marks_remote_locations_deleted(self, client, db, tmp_path):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        local_file = tmp_path / "photo.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db, is_default=False)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id, local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="synced")

        mock_backend = AsyncMock()
        mock_backend.delete = AsyncMock()

        with patch("app.routers.files.settings") as mock_settings, \
             patch("app.routers.files.get_backend_for_type", return_value=mock_backend):
            mock_settings.UPLOAD_DIR = str(tmp_path)
            resp = client.delete(f"/api/v1/files/{cf.id}", headers=headers)

        assert resp.status_code == 204
        db.refresh(loc)
        assert loc.sync_status == "deleted"


class TestGetFileUrlEndpoint:
    def test_get_url_returns_local_when_no_remote(self, client, db, tmp_path):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        local_file = tmp_path / "photo.jpg"
        local_file.write_bytes(b"data")

        cf = _make_cached_file(db, family_id=family_id, user_id=user_id, local_path=str(local_file))

        with patch("app.routers.files.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            resp = client.get(f"/api/v1/files/{cf.id}/url", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "local"
        assert "photo.jpg" in data["url"]

    def test_get_url_returns_remote_when_synced(self, client, db, tmp_path):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        local_file = tmp_path / "photo.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db, is_default=True)
        cf = _make_cached_file(db, family_id=family_id, user_id=user_id, local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="synced")
        loc.remote_url = "http://localhost/20260410/photo.jpg"
        db.commit()

        resp = client.get(f"/api/v1/files/{cf.id}/url", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "remote"
        assert data["url"] == "http://localhost/20260410/photo.jpg"

    def test_get_url_not_found(self, client, db):
        user_id, family_id, token = _register_and_get_ids(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/files/nonexistent/url", headers=headers)
        assert resp.status_code == 404

    def test_get_url_requires_auth(self, client, db):
        resp = client.get("/api/v1/files/some-id/url")
        assert resp.status_code == 401
