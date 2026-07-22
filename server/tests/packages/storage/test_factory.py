"""Tests for packages.storage.factory — 后端类型分发与单例缓存。"""

from __future__ import annotations

import pytest

from packages.storage import factory
from packages.storage.base import StorageBackend
from packages.storage.local import LocalStorageBackend


@pytest.fixture(autouse=True)
def _reset_instances():
    """每个测试前后清空单例缓存，避免跨测试污染。"""
    factory.reset_instances()
    yield
    factory.reset_instances()


class TestGetLocalBackend:
    def test_returns_local_backend(self, tmp_path):
        b = factory.get_local_backend(str(tmp_path))
        assert isinstance(b, LocalStorageBackend)

    def test_singleton_same_upload_dir(self, tmp_path):
        b1 = factory.get_local_backend(str(tmp_path))
        b2 = factory.get_local_backend(str(tmp_path))
        assert b1 is b2

    def test_distinct_per_upload_dir(self, tmp_path):
        b1 = factory.get_local_backend(str(tmp_path / "a"))
        b2 = factory.get_local_backend(str(tmp_path / "b"))
        assert b1 is not b2


class TestGetBackendForType:
    def test_local_dispatch_default_dir(self):
        b = factory.get_backend_for_type("local", {})
        assert isinstance(b, LocalStorageBackend)

    def test_local_dispatch_custom_dir(self, tmp_path):
        b = factory.get_backend_for_type("local", {"upload_dir": str(tmp_path)})
        assert isinstance(b, LocalStorageBackend)

    def test_local_shares_singleton_with_get_local_backend(self, tmp_path):
        direct = factory.get_local_backend(str(tmp_path))
        via_factory = factory.get_backend_for_type("local", {"upload_dir": str(tmp_path)})
        assert direct is via_factory

    def test_github_dispatch(self):
        from packages.storage.github import GitHubStorageBackend

        b = factory.get_backend_for_type(
            "github", {"token": "t", "repo": "owner/repo", "branch": "main"}
        )
        assert isinstance(b, GitHubStorageBackend)

    def test_github_singleton_per_repo_branch(self):
        cfg = {"token": "t", "repo": "owner/repo", "branch": "main"}
        assert factory.get_backend_for_type("github", cfg) is factory.get_backend_for_type("github", cfg)

    def test_github_default_branch_main(self):
        from packages.storage.github import GitHubStorageBackend

        b = factory.get_backend_for_type("github", {"token": "t", "repo": "o/r"})
        assert isinstance(b, GitHubStorageBackend)
        assert b._branch == "main"

    def test_webdav_dispatch(self):
        from packages.storage.webdav import WebDAVStorageBackend

        b = factory.get_backend_for_type(
            "webdav",
            {
                "url": "https://dav.example.com/remote.php/dav",
                "username": "u",
                "password": "p",
            },
        )
        assert isinstance(b, WebDAVStorageBackend)

    def test_webdav_singleton_per_url_user(self):
        cfg = {
            "url": "https://dav.example.com/remote.php/dav",
            "username": "u",
            "password": "p",
        }
        assert factory.get_backend_for_type("webdav", cfg) is factory.get_backend_for_type("webdav", cfg)

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="未知存储后端类型"):
            factory.get_backend_for_type("s3", {})

    def test_all_backends_are_storage_backend(self, tmp_path):
        backends = [
            factory.get_backend_for_type("local", {"upload_dir": str(tmp_path)}),
            factory.get_backend_for_type("github", {"token": "t", "repo": "o/r"}),
            factory.get_backend_for_type(
                "webdav",
                {"url": "https://dav.example.com/dav", "username": "u", "password": "p"},
            ),
        ]
        assert all(isinstance(b, StorageBackend) for b in backends)


class TestResetInstances:
    def test_reset_clears_cache(self, tmp_path):
        b1 = factory.get_local_backend(str(tmp_path))
        factory.reset_instances()
        b2 = factory.get_local_backend(str(tmp_path))
        assert b1 is not b2
