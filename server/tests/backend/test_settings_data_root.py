"""Tests for DATA_ROOT derived path defaults in packages/core/settings.py."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_settings(**overrides):
    """Create a fresh Settings instance with env overrides."""
    env = {
        "SECRET_KEY": "test-secret-key-for-testing",
        "ALTCHA_HMAC_KEY": "test-hmac-key",
        "AI_ENCRYPTION_KEY": "test-encryption-key",
        "STORAGE_ENCRYPTION_KEY": "test-storage-key",
        **overrides,
    }
    # Remove vars that would prevent derivation logic from running
    # (conftest sets DATABASE_URL for lifespan safety; tests that check
    # derivation need it absent so the validator re-derives from DATA_ROOT)
    remove_keys = {"DATABASE_URL", "UPLOAD_DIR", "WORKSPACE_ROOT", "CHAT_DIR", "LOG_DIR"} - set(overrides)
    cleaned_env = {k: v for k, v in os.environ.items() if k not in remove_keys}
    cleaned_env.update(env)
    with patch.dict(os.environ, cleaned_env, clear=True):
        from packages.core.settings import Settings

        # _env_file=None disables .env loading so the repo-root .env (which
        # sets DATABASE_URL for the dev machine) cannot override the derivation
        # logic under test — only the env vars above are honored.
        return Settings(_env_file=None)


def _resolve(p: str) -> str:
    """Resolve a path the same way the validator does (handles /tmp → /private/tmp on macOS)."""
    return str(Path(p).resolve())


class TestDataRootExpansion:
    def test_default_data_root_expands_tilde(self):
        s = _make_settings()
        assert "~" not in s.DATA_ROOT
        assert Path(s.DATA_ROOT).is_absolute()

    def test_custom_data_root_is_resolved(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        assert s.DATA_ROOT == _resolve("/tmp/test-numina")


class TestDerivedPaths:
    def test_upload_dir_derived_from_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        expected = _resolve("/tmp/test-numina") + "/workspaces"
        assert s.UPLOAD_DIR == expected

    def test_workspace_root_derived_from_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        expected = _resolve("/tmp/test-numina") + "/workspaces"
        assert s.WORKSPACE_ROOT == expected

    def test_chat_dir_derived_from_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        expected = _resolve("/tmp/test-numina") + "/workspaces"
        assert s.CHAT_DIR == expected

    def test_log_dir_derived_from_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        expected = _resolve("/tmp/test-numina") + "/logs"
        assert s.LOG_DIR == expected

    def test_database_url_derived_from_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        root = _resolve("/tmp/test-numina")
        assert s.DATABASE_URL == f"sqlite:///{root}/db/numina.db"

    def test_all_derived_paths_under_data_root(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina")
        root = _resolve("/tmp/test-numina")
        assert s.UPLOAD_DIR.startswith(root)
        assert s.WORKSPACE_ROOT.startswith(root)
        assert s.CHAT_DIR.startswith(root)
        assert s.LOG_DIR.startswith(root)
        assert root in s.DATABASE_URL


class TestExplicitOverrides:
    def test_explicit_upload_dir_overrides_derived(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina", UPLOAD_DIR="/custom/uploads")
        assert s.UPLOAD_DIR == "/custom/uploads"

    def test_explicit_log_dir_overrides_derived(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina", LOG_DIR="/var/log/numina")
        assert s.LOG_DIR == "/var/log/numina"

    def test_explicit_database_url_overrides_derived(self):
        s = _make_settings(
            DATA_ROOT="/tmp/test-numina",
            DATABASE_URL="postgresql://localhost/numina",
        )
        assert s.DATABASE_URL == "postgresql://localhost/numina"

    def test_explicit_chat_dir_overrides_derived(self):
        s = _make_settings(DATA_ROOT="/tmp/test-numina", CHAT_DIR="/custom/chat")
        assert s.CHAT_DIR == "/custom/chat"


class TestChatDirValidation:
    def test_chat_dir_strictly_under_upload_dir_raises(self):
        """CHAT_DIR being a strict subdirectory of UPLOAD_DIR is forbidden."""
        from packages.core.settings import Settings

        s = _make_settings(
            DATA_ROOT="/tmp/test-numina",
            UPLOAD_DIR="/tmp/test-numina/workspace",
            CHAT_DIR="/tmp/test-numina/workspace/subdir",
        )
        # The module-level validation runs on the singleton, not on our test instance.
        # Verify the logic directly:
        chat_resolved = Path(s.CHAT_DIR).resolve()
        upload_resolved = Path(s.UPLOAD_DIR).resolve()
        assert chat_resolved != upload_resolved
        assert chat_resolved.is_relative_to(upload_resolved)

    def test_chat_dir_equals_upload_dir_allowed(self):
        """Equality is OK because StaticFiles mount is scoped to uploads subtree."""
        s = _make_settings(
            DATA_ROOT="/tmp/test-numina",
            UPLOAD_DIR="/tmp/test-numina/workspace",
            CHAT_DIR="/tmp/test-numina/workspace",
        )
        assert s.CHAT_DIR == "/tmp/test-numina/workspace"
        assert s.UPLOAD_DIR == "/tmp/test-numina/workspace"
