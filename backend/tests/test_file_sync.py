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
    token = resp.json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    data = me.json()["data"]
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

    def test_sync_job_github_backend_uses_longer_jitter(self, db, tmp_path):
        """GitHub backend triggers write_delay_range of (1.0, 3.0) for jitter."""
        from app.scheduler import file_sync_job

        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"fake-image-data")

        github_backend = StorageBackendModel(
            id="github-test",
            backend_type="github",
            display_name="Test GitHub",
            config='{"token": "ghp_test", "repo": "user/repo", "branch": "main"}',
            is_default=True,
            is_active=True,
        )
        db.add(github_backend)
        db.commit()
        db.refresh(github_backend)

        cf = _make_cached_file(db, family_id="fam-gh", user_id="usr-gh", local_path=str(local_file))
        loc = _make_location(db, cf.id, github_backend.id, sync_status="pending")
        loc_id = loc.id

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(return_value="20260410/test.jpg")
        mock_backend.get_url = MagicMock(return_value="https://raw.githubusercontent.com/user/repo/main/20260410/test.jpg")
        mock_backend.write_delay_range = (1.0, 3.0)

        sleep_calls = []

        async def capture_sleep(delay):
            sleep_calls.append(delay)

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend), \
             patch("app.scheduler.asyncio.sleep", side_effect=capture_sleep):
            run(file_sync_job())

        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.sync_status == "synced"
        assert len(sleep_calls) == 1
        assert 1.0 <= sleep_calls[0] <= 3.0

    def test_sync_job_save_timeout_increments_retry(self, db, tmp_path):
        """backend.save() timeout increments retry_count and records error."""
        from app.scheduler import file_sync_job

        local_file = tmp_path / "test.jpg"
        local_file.write_bytes(b"data")

        backend = _make_backend(db)
        cf = _make_cached_file(db, family_id="fam-timeout", user_id="usr-timeout", local_path=str(local_file))
        loc = _make_location(db, cf.id, backend.id, sync_status="pending")
        loc_id = loc.id

        async def slow_save(*args, **kwargs):
            raise asyncio.TimeoutError()

        mock_backend = AsyncMock()
        mock_backend.save = AsyncMock(side_effect=slow_save)
        mock_backend.write_delay_range = (0.2, 1.0)

        with patch("app.scheduler.SessionLocal", return_value=db), \
             patch("app.scheduler.get_backend_for_type", return_value=mock_backend), \
             patch("app.scheduler.asyncio.sleep", new_callable=AsyncMock):
            run(file_sync_job())

        loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
        assert loc_updated.retry_count == 1
        assert "超时" in (loc_updated.last_error or "")
        assert loc_updated.sync_status == "pending"


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
        data = resp.json()["data"]
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
        data = resp.json()["data"]
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
