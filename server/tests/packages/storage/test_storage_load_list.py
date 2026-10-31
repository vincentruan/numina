"""Tests for StorageBackend.load() and StorageBackend.list().

These two methods make a backup discoverable and retrievable from remote
storage alone — the only source of truth once the database holding the
backup records is gone. Each backend maps "not found" to FileNotFoundError,
auth failures to StorageAuthError, and transport failures to
StorageConnectionError, so callers can distinguish them without knowing
which backend is in use.
"""

from __future__ import annotations

import httpx
import pytest

from packages.storage.base import StorageAuthError, StorageConnectionError
from packages.storage.github import GitHubStorageBackend
from packages.storage.local import LocalStorageBackend
from packages.storage.webdav import WebDAVStorageBackend


def _gh_backend() -> GitHubStorageBackend:
    return GitHubStorageBackend(token="t0ken", repo="owner/repo", branch="main")


def _gh_response(status_code: int, *, json_body=None, content: bytes | None = None) -> httpx.Response:
    kwargs: dict = {"request": httpx.Request("GET", "https://api.github.com/x")}
    if json_body is not None:
        kwargs["json"] = json_body
    elif content is not None:
        kwargs["content"] = content
    else:
        kwargs["json"] = {}
    return httpx.Response(status_code, **kwargs)


class TestGitHubLoad:
    async def test_returns_file_bytes(self):
        backend = _gh_backend()
        payload = b'{"export_version": "2.0"}'
        response = _gh_response(200, content=payload)
        response.request = httpx.Request("GET", "https://api.github.com/x")

        def handler(request):
            return httpx.Response(200, content=payload, request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
            headers={"Authorization": "Bearer t0ken"},
        )
        try:
            assert await backend.load("backups/20261030/120000/numina_backup_1.json") == payload
        finally:
            await backend._client.aclose()

    async def test_missing_file_raises_file_not_found(self):
        backend = _gh_backend()

        def handler(request):
            return httpx.Response(404, json={}, request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        )
        try:
            with pytest.raises(FileNotFoundError):
                await backend.load("backups/missing.json")
        finally:
            await backend._client.aclose()

    async def test_auth_failure_raises_auth_error(self):
        backend = _gh_backend()

        def handler(request):
            return httpx.Response(401, json={}, request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        )
        try:
            with pytest.raises(StorageAuthError):
                await backend.load("backups/x.json")
        finally:
            await backend._client.aclose()

    async def test_transport_failure_raises_connection_error(self):
        backend = _gh_backend()

        def handler(request):
            raise httpx.ConnectError("boom", request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        )
        try:
            with pytest.raises(StorageConnectionError):
                await backend.load("backups/x.json")
        finally:
            await backend._client.aclose()


class TestGitHubList:
    async def test_lists_directory_entries(self):
        backend = _gh_backend()
        entries = [
            {
                "name": "numina_backup_1.json",
                "path": "backups/20261030/120000/numina_backup_1.json",
                "size": 4096,
                "type": "file",
            },
            {
                "name": "143000",
                "path": "backups/20261030/143000",
                "size": 0,
                "type": "dir",
            },
        ]

        def handler(request):
            return httpx.Response(200, json=entries, request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        )
        try:
            listed = await backend.list("backups/20261030")
        finally:
            await backend._client.aclose()

        assert [item["path"] for item in listed] == [e["path"] for e in entries]
        assert listed[0]["size"] == 4096
        assert "last_modified" in listed[0]

    async def test_missing_prefix_returns_empty_list(self):
        backend = _gh_backend()

        def handler(request):
            return httpx.Response(404, json={}, request=request)

        backend._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        )
        try:
            assert await backend.list("backups/none") == []
        finally:
            await backend._client.aclose()


class TestLocalLoad:
    async def test_reads_saved_file(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        remote = await backend.save(b"payload", "numina_backup_1.json", "backups/20261030")

        assert await backend.load(remote) == b"payload"

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            await backend.load("backups/20261030/nope.json")

    async def test_path_traversal_is_rejected(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            await backend.load("../../etc/passwd")


class TestLocalList:
    async def test_lists_files_under_prefix(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        one = await backend.save(b"a", "one.json", "backups/20261030/120000")
        two = await backend.save(b"bb", "two.json", "backups/20261030/130000")

        listed = await backend.list("images/backups/20261030")

        paths = {item["path"] for item in listed}
        assert paths == {one, two}
        sizes = {item["path"]: item["size"] for item in listed}
        assert sizes[one] == 1
        assert sizes[two] == 2
        assert all("last_modified" in item for item in listed)

    async def test_missing_prefix_returns_empty_list(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))

        assert await backend.list("backups/none") == []


def _webdav_backend(handler) -> WebDAVStorageBackend:
    backend = WebDAVStorageBackend(
        base_url="https://dav.example.com/remote",
        username="u",
        password="p",
    )
    backend._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://dav.example.com"
    )
    return backend


class TestWebDAVLoad:
    async def test_returns_file_bytes(self):
        backend = _webdav_backend(
            lambda request: httpx.Response(200, content=b"backup", request=request)
        )
        try:
            assert await backend.load("backups/x.json") == b"backup"
        finally:
            await backend._client.aclose()

    async def test_missing_file_raises_file_not_found(self):
        backend = _webdav_backend(
            lambda request: httpx.Response(404, request=request)
        )
        try:
            with pytest.raises(FileNotFoundError):
                await backend.load("backups/missing.json")
        finally:
            await backend._client.aclose()

    async def test_auth_failure_raises_auth_error(self):
        backend = _webdav_backend(
            lambda request: httpx.Response(401, request=request)
        )
        try:
            with pytest.raises(StorageAuthError):
                await backend.load("backups/x.json")
        finally:
            await backend._client.aclose()


class TestWebDAVList:
    async def test_parses_propfind_multistatus(self):
        multistatus = """<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:">
  <D:response>
    <D:href>/remote/backups/20261030/</D:href>
    <D:propstat><D:prop>
      <D:getcontentlength>0</D:getcontentlength>
    </D:prop></D:propstat>
  </D:response>
  <D:response>
    <D:href>/remote/backups/20261030/120000/numina_backup_1.json</D:href>
    <D:propstat><D:prop>
      <D:getcontentlength>4096</D:getcontentlength>
      <D:getlastmodified>Thu, 30 Oct 2026 12:00:00 GMT</D:getlastmodified>
    </D:prop></D:propstat>
  </D:response>
</D:multistatus>"""
        backend = _webdav_backend(
            lambda request: httpx.Response(
                207, text=multistatus, request=request
            )
        )
        try:
            listed = await backend.list("backups/20261030")
        finally:
            await backend._client.aclose()

        assert len(listed) == 1
        assert listed[0]["path"] == "backups/20261030/120000/numina_backup_1.json"
        assert listed[0]["size"] == 4096
        assert listed[0]["last_modified"] == "Thu, 30 Oct 2026 12:00:00 GMT"

    async def test_missing_prefix_returns_empty_list(self):
        backend = _webdav_backend(
            lambda request: httpx.Response(404, request=request)
        )
        try:
            assert await backend.list("backups/none") == []
        finally:
            await backend._client.aclose()


class TestLocalBackupLayout:
    """Backups written without a user id land under the legacy images/ segment."""

    async def test_list_finds_backup_written_by_save(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        path = await backend.save(
            b"backup", "numina_backup_1.json", "backups/20261030/120000", family_id="1"
        )

        listed = await backend.list("backups/20261030")

        assert [e["path"] for e in listed] == [path]
        assert await backend.load(path) == b"backup"
