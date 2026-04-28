"""Tests for GitHubStorageBackend."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.storage.base import (
    StorageConflictError,
    StorageConnectionError,
    StorageRateLimitError,
)
from app.services.storage.github import GitHubStorageBackend


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_response(status_code: int, json_data: dict | None = None, headers: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


@pytest.fixture
def backend():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        b = GitHubStorageBackend(token="tok", repo="owner/repo", branch="main")
        b._client = mock_client
        yield b


class TestGitHubStorageBackend:
    def test_save_201_returns_remote_path_and_caches_sha(self, backend):
        resp = make_response(
            201,
            {"content": {"sha": "abc123"}},
            {"x-ratelimit-remaining": "59"},
        )
        backend._client.put = AsyncMock(return_value=resp)

        result = run(backend.save(b"data", "photo.jpg", "20260410"))

        assert result == "20260410/photo.jpg"
        assert backend._sha_cache["20260410/photo.jpg"] == "abc123"

    def test_save_existing_path_includes_sha_in_put_body(self, backend):
        backend._sha_cache["20260410/photo.jpg"] = "existing_sha"
        resp = make_response(200, {"content": {"sha": "new_sha"}}, {"x-ratelimit-remaining": "58"})
        backend._client.put = AsyncMock(return_value=resp)

        run(backend.save(b"updated", "photo.jpg", "20260410"))

        call_kwargs = backend._client.put.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["json"]
        assert body["sha"] == "existing_sha"

    def test_get_url_returns_raw_githubusercontent_url(self, backend):
        url = backend.get_url("20260410/photo.jpg")
        assert url == "https://raw.githubusercontent.com/owner/repo/main/20260410/photo.jpg"

    def test_save_409_refetches_sha_and_retries_success(self, backend):
        conflict_resp = make_response(409, {}, {"x-ratelimit-remaining": "50"})
        success_resp = make_response(201, {"content": {"sha": "fresh_sha"}}, {"x-ratelimit-remaining": "49"})
        get_resp = make_response(200, {"sha": "current_sha"}, {"x-ratelimit-remaining": "48"})

        backend._client.put = AsyncMock(side_effect=[conflict_resp, success_resp])
        backend._client.get = AsyncMock(return_value=get_resp)

        result = run(backend.save(b"data", "photo.jpg", "20260410"))

        assert result == "20260410/photo.jpg"
        assert backend._sha_cache["20260410/photo.jpg"] == "fresh_sha"
        assert backend._client.put.call_count == 2

    def test_save_409_three_times_raises_conflict_error(self, backend):
        conflict_resp = make_response(409, {}, {"x-ratelimit-remaining": "50"})
        get_resp = make_response(200, {"sha": "some_sha"}, {"x-ratelimit-remaining": "49"})

        backend._client.put = AsyncMock(return_value=conflict_resp)
        backend._client.get = AsyncMock(return_value=get_resp)

        with pytest.raises(StorageConflictError):
            run(backend.save(b"data", "photo.jpg", "20260410"))

        assert backend._client.put.call_count == 3

    def test_save_rate_limit_zero_raises_rate_limit_error(self, backend):
        resp = make_response(
            201,
            {"content": {"sha": "abc"}},
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"},
        )
        backend._client.put = AsyncMock(return_value=resp)

        with pytest.raises(StorageRateLimitError) as exc_info:
            run(backend.save(b"data", "photo.jpg", "20260410"))

        assert exc_info.value.reset_at == 1700000000

    def test_delete_with_sha_in_cache_calls_delete_with_correct_sha(self, backend):
        backend._sha_cache["20260410/photo.jpg"] = "cached_sha"
        del_resp = make_response(200, {}, {"x-ratelimit-remaining": "55"})
        backend._client.request = AsyncMock(return_value=del_resp)

        run(backend.delete("20260410/photo.jpg"))

        call_kwargs = backend._client.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[2] if len(call_kwargs.args) > 2 else call_kwargs.kwargs["json"]
        assert body["sha"] == "cached_sha"
        assert "20260410/photo.jpg" not in backend._sha_cache

    def test_delete_404_treated_as_success(self, backend):
        backend._sha_cache["20260410/photo.jpg"] = "some_sha"
        del_resp = make_response(404, {}, {"x-ratelimit-remaining": "55"})
        backend._client.request = AsyncMock(return_value=del_resp)

        # Should not raise
        run(backend.delete("20260410/photo.jpg"))

    def test_save_transport_error_raises_connection_error(self, backend):
        backend._client.put = AsyncMock(side_effect=httpx.TransportError("connection refused"))

        with pytest.raises(StorageConnectionError):
            run(backend.save(b"data", "photo.jpg", "20260410"))
