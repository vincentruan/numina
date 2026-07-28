"""Tests for seed_storage_backends — env-var driven storage backend seeding."""

from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.seed.storage_backends import seed_storage_backends
from apps.backend.app.services.storage.config_crypto import decrypt_config
from apps.backend.app.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch(monkeypatch, **kwargs):
    """Patch settings fields for the duration of a test."""
    for key, value in kwargs.items():
        monkeypatch.setattr(settings, key, value)


def _github_defaults(monkeypatch, **overrides):
    attrs = dict(
        STORAGE_BACKEND_TYPE="github",
        STORAGE_BACKEND_NAME="GitHub Backup",
        STORAGE_BACKEND_IS_DEFAULT=True,
        STORAGE_BACKEND_IS_ACTIVE=True,
        STORAGE_GITHUB_REPO_OWNER="acme",
        STORAGE_GITHUB_REPO_NAME="backup",
        STORAGE_GITHUB_BRANCH="main",
        STORAGE_GITHUB_TOKEN="ghp_test",
    )
    attrs.update(overrides)
    _patch(monkeypatch, **attrs)


def _webdav_defaults(monkeypatch, **overrides):
    attrs = dict(
        STORAGE_BACKEND_TYPE="webdav",
        STORAGE_BACKEND_NAME="WebDAV Cloud",
        STORAGE_BACKEND_IS_DEFAULT=False,
        STORAGE_BACKEND_IS_ACTIVE=True,
        STORAGE_WEBDAV_BASE_URL="https://dav.example.com",
        STORAGE_WEBDAV_USERNAME="user",
        STORAGE_WEBDAV_PASSWORD="pass",
    )
    attrs.update(overrides)
    _patch(monkeypatch, **attrs)


def _count(db) -> int:
    return db.query(StorageBackend).count()


def _get(db, name: str) -> StorageBackend | None:
    return db.query(StorageBackend).filter_by(display_name=name).first()


# ---------------------------------------------------------------------------
# Skip when STORAGE_BACKEND_TYPE is empty
# ---------------------------------------------------------------------------

class TestSkipWhenNotConfigured:
    def test_empty_type_skips(self, db, monkeypatch):
        _patch(monkeypatch, STORAGE_BACKEND_TYPE="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_no_backend_created_when_type_blank(self, db, monkeypatch):
        _patch(monkeypatch, STORAGE_BACKEND_TYPE="")
        seed_storage_backends(db)
        seed_storage_backends(db)  # idempotent
        assert _count(db) == 0


# ---------------------------------------------------------------------------
# Invalid type rejected
# ---------------------------------------------------------------------------

class TestInvalidType:
    def test_unknown_type_skips(self, db, monkeypatch):
        _patch(monkeypatch, STORAGE_BACKEND_TYPE="s3")
        seed_storage_backends(db)
        assert _count(db) == 0


# ---------------------------------------------------------------------------
# GitHub backend
# ---------------------------------------------------------------------------

class TestGitHubBackend:
    def test_creates_backend(self, db, monkeypatch):
        _github_defaults(monkeypatch)
        seed_storage_backends(db)

        backend = _get(db, "GitHub Backup")
        assert backend is not None
        assert backend.backend_type == "github"
        assert backend.is_default is True
        assert backend.is_active is True

    def test_credentials_encrypted(self, db, monkeypatch):
        _github_defaults(monkeypatch)
        seed_storage_backends(db)

        backend = _get(db, "GitHub Backup")
        assert backend.config is not None
        # Must not store plaintext token
        assert "ghp_test" not in backend.config

        decrypted = decrypt_config(backend.config)
        assert decrypted is not None
        assert decrypted["token"] == "ghp_test"
        assert decrypted["repo_owner"] == "acme"
        assert decrypted["repo_name"] == "backup"
        assert decrypted["branch"] == "main"

    def test_skips_when_token_missing(self, db, monkeypatch):
        _github_defaults(monkeypatch, STORAGE_GITHUB_TOKEN="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_skips_when_repo_owner_missing(self, db, monkeypatch):
        _github_defaults(monkeypatch, STORAGE_GITHUB_REPO_OWNER="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_skips_when_repo_name_missing(self, db, monkeypatch):
        _github_defaults(monkeypatch, STORAGE_GITHUB_REPO_NAME="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_default_name_fallback(self, db, monkeypatch):
        _github_defaults(monkeypatch, STORAGE_BACKEND_NAME="")
        seed_storage_backends(db)
        assert _get(db, "GITHUB") is not None

    def test_idempotent_no_change(self, db, monkeypatch):
        _github_defaults(monkeypatch)
        seed_storage_backends(db)
        seed_storage_backends(db)
        assert _count(db) == 1


# ---------------------------------------------------------------------------
# WebDAV backend
# ---------------------------------------------------------------------------

class TestWebDAVBackend:
    def test_creates_backend(self, db, monkeypatch):
        _webdav_defaults(monkeypatch)
        seed_storage_backends(db)

        backend = _get(db, "WebDAV Cloud")
        assert backend is not None
        assert backend.backend_type == "webdav"
        assert backend.is_default is False
        assert backend.is_active is True

    def test_credentials_encrypted(self, db, monkeypatch):
        _webdav_defaults(monkeypatch)
        seed_storage_backends(db)

        backend = _get(db, "WebDAV Cloud")
        assert backend.config is not None
        assert "pass" not in backend.config

        decrypted = decrypt_config(backend.config)
        assert decrypted is not None
        assert decrypted["base_url"] == "https://dav.example.com"
        assert decrypted["username"] == "user"
        assert decrypted["password"] == "pass"

    def test_skips_when_base_url_missing(self, db, monkeypatch):
        _webdav_defaults(monkeypatch, STORAGE_WEBDAV_BASE_URL="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_skips_when_username_missing(self, db, monkeypatch):
        _webdav_defaults(monkeypatch, STORAGE_WEBDAV_USERNAME="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_skips_when_password_missing(self, db, monkeypatch):
        _webdav_defaults(monkeypatch, STORAGE_WEBDAV_PASSWORD="")
        seed_storage_backends(db)
        assert _count(db) == 0

    def test_idempotent_no_change(self, db, monkeypatch):
        _webdav_defaults(monkeypatch)
        seed_storage_backends(db)
        seed_storage_backends(db)
        assert _count(db) == 1


# ---------------------------------------------------------------------------
# Update behaviour
# ---------------------------------------------------------------------------

class TestUpdateExisting:
    def test_config_updated_when_token_changes(self, db, monkeypatch):
        _github_defaults(monkeypatch)
        seed_storage_backends(db)

        _github_defaults(monkeypatch, STORAGE_GITHUB_TOKEN="ghp_new")
        seed_storage_backends(db)

        assert _count(db) == 1
        backend = _get(db, "GitHub Backup")
        decrypted = decrypt_config(backend.config)
        assert decrypted["token"] == "ghp_new"

    def test_flags_updated_when_config_unchanged(self, db, monkeypatch):
        _github_defaults(monkeypatch, STORAGE_BACKEND_IS_DEFAULT=True)
        seed_storage_backends(db)

        _github_defaults(monkeypatch, STORAGE_BACKEND_IS_DEFAULT=False)
        seed_storage_backends(db)

        backend = _get(db, "GitHub Backup")
        assert backend.is_default is False

    def test_no_spurious_write_when_nothing_changed(self, db, monkeypatch):
        _github_defaults(monkeypatch)
        seed_storage_backends(db)
        first_updated_at = _get(db, "GitHub Backup").updated_at

        seed_storage_backends(db)
        second_updated_at = _get(db, "GitHub Backup").updated_at

        # SQLite updated_at has second-level granularity, so equal timestamps
        # prove no UPDATE was issued in the same second.
        assert first_updated_at == second_updated_at

    def test_preserves_other_backends_in_db(self, db, monkeypatch):
        # Manually insert a backend not managed by env vars
        other = StorageBackend(
            backend_type="local",
            display_name="Local Storage",
            config=None,
            is_default=False,
            is_active=True,
        )
        db.add(other)
        db.commit()

        _github_defaults(monkeypatch)
        seed_storage_backends(db)

        assert _count(db) == 2
        assert _get(db, "Local Storage") is not None


# ---------------------------------------------------------------------------
# Multiple-default warning (does not raise, just warns)
# ---------------------------------------------------------------------------

class TestMultipleDefaultWarning:
    def test_warns_when_multiple_defaults_exist(self, db, monkeypatch, caplog):
        # Insert a pre-existing default backend
        existing_default = StorageBackend(
            backend_type="local",
            display_name="Local Storage",
            config=None,
            is_default=True,
            is_active=True,
        )
        db.add(existing_default)
        db.commit()

        _github_defaults(monkeypatch, STORAGE_BACKEND_IS_DEFAULT=True)
        import logging
        with caplog.at_level(logging.WARNING):
            seed_storage_backends(db)

        assert any("多个默认存储后端" in r.message for r in caplog.records)
