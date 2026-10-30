"""Tests for GitHubStorageBackend size-limit handling (issue #158).

GitHub Contents API rejects payloads over 1MB. Base64 expands content by ~33%,
so the backend must reject raw content above 750KB *before* making a request,
and must surface server-side 413/422 responses as StorageFileSizeError rather
than the misleading StorageConflictError.
"""

from __future__ import annotations

import base64

import httpx
import pytest

from packages.storage.base import StorageFileSizeError
from packages.storage.github import _MAX_CONTENT_BYTES, GitHubStorageBackend


def _make_backend() -> GitHubStorageBackend:
    return GitHubStorageBackend(token="t0ken", repo="owner/repo", branch="main")


def _response(status_code: int, *, json_body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json_body or {},
        request=httpx.Request("PUT", "https://api.github.com/x"),
    )


class TestPreflightSizeCheck:
    """Client-side rejection happens before any network call."""

    async def test_content_over_limit_raises_file_size_error(self):
        backend = _make_backend()
        oversized = b"x" * (_MAX_CONTENT_BYTES + 1)

        with pytest.raises(StorageFileSizeError) as exc_info:
            await backend.save(oversized, "big.png", "20260101")

        assert exc_info.value.file_size == len(oversized)
        assert exc_info.value.max_size == _MAX_CONTENT_BYTES

    async def test_oversized_file_never_reaches_network(self):
        backend = _make_backend()
        called = False

        async def _fail_put(*args, **kwargs):  # pragma: no cover - must not run
            nonlocal called
            called = True
            return _response(201, json_body={"content": {"sha": "abc"}})

        backend._client.put = _fail_put  # type: ignore[method-assign]

        with pytest.raises(StorageFileSizeError):
            await backend.save(b"x" * (_MAX_CONTENT_BYTES + 1), "big.png", "20260101")

        assert called is False

    async def test_content_at_exact_limit_is_accepted(self):
        backend = _make_backend()
        content = b"x" * _MAX_CONTENT_BYTES

        async def _ok_put(*args, **kwargs):
            return _response(201, json_body={"content": {"sha": "abc"}})

        backend._client.put = _ok_put  # type: ignore[method-assign]

        remote = await backend.save(content, "edge.png", "20260101")
        assert remote == "20260101/edge.png"

    async def test_error_message_names_the_file_and_sizes(self):
        backend = _make_backend()
        with pytest.raises(StorageFileSizeError) as exc_info:
            await backend.save(b"x" * (_MAX_CONTENT_BYTES + 1), "holiday.jpg", "20260101")

        message = str(exc_info.value)
        assert "holiday.jpg" in message
        assert str(_MAX_CONTENT_BYTES) in message

    async def test_file_size_error_is_a_storage_error(self):
        from packages.storage.base import StorageError

        assert issubclass(StorageFileSizeError, StorageError)


class TestServerSideSizeRejection:
    """413/422 from GitHub map to StorageFileSizeError, not StorageConflictError."""

    @pytest.mark.parametrize("status_code", [413, 422])
    async def test_payload_too_large_raises_file_size_error(self, status_code):
        backend = _make_backend()

        async def _rejecting_put(*args, **kwargs):
            return _response(status_code, json_body={"message": "too large"})

        backend._client.put = _rejecting_put  # type: ignore[method-assign]

        with pytest.raises(StorageFileSizeError) as exc_info:
            await backend.save(b"content", "f.png", "20260101")

        assert exc_info.value.file_size == len(b"content")

    async def test_size_rejection_is_not_retried(self):
        backend = _make_backend()
        attempts = 0

        async def _rejecting_put(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            return _response(413, json_body={"message": "too large"})

        backend._client.put = _rejecting_put  # type: ignore[method-assign]

        with pytest.raises(StorageFileSizeError):
            await backend.save(b"content", "f.png", "20260101")

        # Permanent failure — retrying would only burn API quota.
        assert attempts == 1


class TestBase64ExpansionAssumption:
    """Guard the 750KB threshold: base64 of 750KB must stay under GitHub's 1MB."""

    def test_max_content_fits_after_base64(self):
        encoded = base64.b64encode(b"x" * _MAX_CONTENT_BYTES)
        assert len(encoded) < 1024 * 1024
