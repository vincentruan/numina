"""Tests for WebDAVStorageBackend."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.storage.base import StorageAuthError, StorageConnectionError
from app.services.storage.webdav import WebDAVStorageBackend


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def make_backend() -> WebDAVStorageBackend:
    return WebDAVStorageBackend(
        base_url="https://dav.example.com/files/",
        username="user",
        password="pass",
    )


class TestWebDAVStorageBackend:
    def test_save_mkcol_201_put_201_returns_remote_path(self):
        backend = make_backend()
        with patch.object(backend._client, "request", new=AsyncMock(return_value=make_response(201))), \
             patch.object(backend._client, "put", new=AsyncMock(return_value=make_response(201))):
            result = run(backend.save(b"data", "photo.jpg", "20260410"))
        assert result == "20260410/photo.jpg"

    def test_ensure_path_mkcol_405_treated_as_success(self):
        backend = make_backend()
        with patch.object(backend._client, "request", new=AsyncMock(return_value=make_response(405))):
            # Should not raise
            run(backend._ensure_path("20260410"))

    def test_save_put_401_raises_storage_auth_error(self):
        backend = make_backend()
        with patch.object(backend._client, "request", new=AsyncMock(return_value=make_response(201))), \
             patch.object(backend._client, "put", new=AsyncMock(return_value=make_response(401))):
            with pytest.raises(StorageAuthError):
                run(backend.save(b"data", "photo.jpg", "20260410"))

    def test_save_transport_error_raises_storage_connection_error(self):
        backend = make_backend()
        with patch.object(backend._client, "request", new=AsyncMock(return_value=make_response(201))), \
             patch.object(backend._client, "put", new=AsyncMock(side_effect=httpx.TransportError("conn failed"))):
            with pytest.raises(StorageConnectionError):
                run(backend.save(b"data", "photo.jpg", "20260410"))

    def test_delete_204_success(self):
        backend = make_backend()
        with patch.object(backend._client, "delete", new=AsyncMock(return_value=make_response(204))):
            run(backend.delete("20260410/photo.jpg"))  # should not raise

    def test_delete_404_treated_as_success(self):
        backend = make_backend()
        with patch.object(backend._client, "delete", new=AsyncMock(return_value=make_response(404))):
            run(backend.delete("20260410/photo.jpg"))  # should not raise

    def test_get_url_returns_base_url_plus_path(self):
        backend = make_backend()
        url = backend.get_url("20260410/photo.jpg")
        assert url == "https://dav.example.com/files/20260410/photo.jpg"

    def test_save_put_204_overwrite_success(self):
        backend = make_backend()
        with patch.object(backend._client, "request", new=AsyncMock(return_value=make_response(201))), \
             patch.object(backend._client, "put", new=AsyncMock(return_value=make_response(204))):
            result = run(backend.save(b"updated", "photo.jpg", "20260410"))
        assert result == "20260410/photo.jpg"
