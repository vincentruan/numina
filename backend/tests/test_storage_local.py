"""Tests for LocalStorageBackend."""
import asyncio
import os

import pytest

from app.services.storage.local import LocalStorageBackend
from app.services.storage.factory import get_local_backend, get_backend_for_type, reset_instances


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def upload_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def backend(upload_dir):
    return LocalStorageBackend(upload_dir)


class TestLocalStorageBackend:
    def test_save_creates_file_at_correct_path(self, backend, upload_dir):
        remote_path = run(backend.save(b"hello", "photo.jpg", "20260410"))
        assert remote_path == "images/20260410/photo.jpg"
        full_path = os.path.join(upload_dir, "images", "20260410", "photo.jpg")
        assert os.path.exists(full_path)
        with open(full_path, "rb") as f:
            assert f.read() == b"hello"

    def test_save_creates_nested_directories(self, backend, upload_dir):
        run(backend.save(b"data", "file.png", "20260101"))
        assert os.path.isdir(os.path.join(upload_dir, "images", "20260101"))

    def test_save_overwrites_existing_file(self, backend, upload_dir):
        run(backend.save(b"original", "photo.jpg", "20260410"))
        run(backend.save(b"updated", "photo.jpg", "20260410"))
        full_path = os.path.join(upload_dir, "images", "20260410", "photo.jpg")
        with open(full_path, "rb") as f:
            assert f.read() == b"updated"

    def test_get_url_returns_uploads_prefix(self, backend):
        url = backend.get_url("images/20260410/photo.jpg")
        assert url == "/uploads/images/20260410/photo.jpg"

    def test_delete_removes_file(self, backend, upload_dir):
        run(backend.save(b"data", "photo.jpg", "20260410"))
        run(backend.delete("images/20260410/photo.jpg"))
        full_path = os.path.join(upload_dir, "images", "20260410", "photo.jpg")
        assert not os.path.exists(full_path)

    def test_delete_nonexistent_does_not_raise(self, backend):
        # Should log warning but not raise
        run(backend.delete("images/20260410/nonexistent.jpg"))

    def test_save_returns_correct_path_format(self, backend):
        remote_path = run(backend.save(b"x", "abc123.webp", "20261231"))
        assert remote_path == "images/20261231/abc123.webp"


class TestStorageFactory:
    def setup_method(self):
        reset_instances()

    def test_get_local_backend_returns_local_instance(self, tmp_path):
        backend = get_local_backend(str(tmp_path))
        assert isinstance(backend, LocalStorageBackend)

    def test_get_local_backend_singleton(self, tmp_path):
        b1 = get_local_backend(str(tmp_path))
        b2 = get_local_backend(str(tmp_path))
        assert b1 is b2

    def test_get_backend_for_type_local(self, tmp_path):
        backend = get_backend_for_type("local", {"upload_dir": str(tmp_path)})
        assert isinstance(backend, LocalStorageBackend)

    def test_get_backend_for_type_unknown_raises(self):
        with pytest.raises(ValueError, match="未知存储后端类型"):
            get_backend_for_type("s3", {})
