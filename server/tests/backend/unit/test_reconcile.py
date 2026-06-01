"""Tests for the reconciliation framework."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.backend.app.database import Base
from apps.backend.app.reconcile.lock import TableBasedLock, create_lock_provider
from apps.backend.app.reconcile.resources.database_seed import DatabaseSeedResource
from apps.backend.app.reconcile.resources.directory import DirectoryResource
from apps.backend.app.reconcile.resources.feature_flag import (
    FeatureFlagResource,
    _disabled_reasons,
    _feature_flags,
    is_feature_enabled,
)
from apps.backend.app.reconcile.resources.file import FileResource
from apps.backend.app.reconcile.resources.remote_asset import RemoteAssetResource
from apps.backend.app.reconcile.runner import DesiredStateRunner, RunMode
from apps.backend.app.reconcile.state_store import StateStore
from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceStatus,
    ResourceType,
)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session_ = sessionmaker(bind=db_engine)
    session = Session_()
    yield session
    session.close()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(autouse=True)
def reset_feature_flags():
    """Reset feature flag state between tests."""
    _feature_flags.clear()
    _disabled_reasons.clear()
    yield
    _feature_flags.clear()
    _disabled_reasons.clear()


# ---------------------------------------------------------------------------
# DirectoryResource tests
# ---------------------------------------------------------------------------


class TestDirectoryResource:
    def test_check_existing_writable_dir(self, tmp_dir):
        res = DirectoryResource(name="test_dir", path=tmp_dir)
        result = res.check()
        assert result.status == ResourceStatus.VERIFIED

    def test_check_missing_dir(self, tmp_dir):
        missing = tmp_dir / "nonexistent"
        res = DirectoryResource(name="test_dir", path=missing)
        result = res.check()
        assert result.status == ResourceStatus.DRIFTED

    def test_apply_creates_dir(self, tmp_dir):
        target = tmp_dir / "new" / "nested"
        res = DirectoryResource(name="test_dir", path=target)
        result = res.apply()
        assert result.status == ResourceStatus.VERIFIED
        assert target.is_dir()

    def test_check_file_not_dir(self, tmp_dir):
        file_path = tmp_dir / "afile"
        file_path.write_text("x")
        res = DirectoryResource(name="test_dir", path=file_path)
        result = res.check()
        assert result.status == ResourceStatus.FAILED
        assert "not a directory" in result.error


# ---------------------------------------------------------------------------
# FileResource tests
# ---------------------------------------------------------------------------


class TestFileResource:
    def test_check_missing_file(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: "key: value\n",
        )
        result = res.check()
        assert result.status == ResourceStatus.DRIFTED

    def test_apply_creates_file(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        content = "key: value\n"
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: content,
        )
        result = res.apply()
        assert result.status == ResourceStatus.VERIFIED
        assert target.exists()
        assert "key: value" in target.read_text()

    def test_apply_does_not_overwrite_user_modified(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        target.write_text("user modified content\n")
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: "system content\n",
        )
        result = res.check()
        # No managed marker → skipped
        assert result.status == ResourceStatus.SKIPPED

    def test_apply_updates_managed_file(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        target.write_text("# managed-by: numina-reconcile\nold content\n")
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: "new content\n",
        )
        result = res.check()
        assert result.status == ResourceStatus.DRIFTED
        result = res.apply()
        assert result.status == ResourceStatus.VERIFIED
        assert "new content" in target.read_text()

    def test_apply_creates_backup(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        target.write_text("# managed-by: numina-reconcile\nold\n")
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: "new\n",
        )
        res.apply()
        backup = target.with_suffix(".yaml.bak")
        assert backup.exists()
        assert "old" in backup.read_text()

    def test_idempotent_no_change(self, tmp_dir):
        target = tmp_dir / "config.yaml"
        content = "stable content\n"
        res = FileResource(
            name="test_file",
            path=target,
            content_provider=lambda: content,
            add_managed_marker=False,
        )
        res.apply()
        # Second apply should verify without changes
        result = res.check()
        assert result.status == ResourceStatus.VERIFIED


# ---------------------------------------------------------------------------
# RemoteAssetResource tests
# ---------------------------------------------------------------------------


class TestRemoteAssetResource:
    def test_check_existing_file_correct_checksum(self, tmp_dir):
        target = tmp_dir / "asset.bin"
        content = b"hello world"
        target.write_bytes(content)
        import hashlib
        sha = hashlib.sha256(content).hexdigest()

        res = RemoteAssetResource(
            name="test_asset",
            local_path=target,
            url="https://example.com/asset.bin",
            sha256=sha,
        )
        result = res.check()
        assert result.status == ResourceStatus.VERIFIED

    def test_check_missing_file(self, tmp_dir):
        target = tmp_dir / "missing.bin"
        res = RemoteAssetResource(
            name="test_asset",
            local_path=target,
            url="https://example.com/asset.bin",
        )
        result = res.check()
        assert result.status == ResourceStatus.DRIFTED

    def test_apply_offline_mode_fails_gracefully(self, tmp_dir):
        target = tmp_dir / "missing.bin"
        res = RemoteAssetResource(
            name="test_asset",
            local_path=target,
            url="https://example.com/asset.bin",
            offline=True,
            feature_flag="some_feature",
        )
        result = res.apply()
        assert result.status == ResourceStatus.FAILED
        assert "offline" in result.error.lower()
        assert result.feature_disabled == "some_feature"

    def test_apply_uses_cache(self, tmp_dir):
        target = tmp_dir / "asset.bin"
        cache_dir = tmp_dir / "cache"
        cache_dir.mkdir()
        content = b"cached content"
        import hashlib
        sha = hashlib.sha256(content).hexdigest()

        # Pre-populate cache
        cache_file = cache_dir / f"test_asset.{sha[:12]}"
        cache_file.write_bytes(content)

        res = RemoteAssetResource(
            name="test_asset",
            local_path=target,
            url="https://example.com/asset.bin",
            sha256=sha,
            cache_dir=cache_dir,
        )
        result = res.apply()
        assert result.status == ResourceStatus.VERIFIED
        assert target.read_bytes() == content


# ---------------------------------------------------------------------------
# DatabaseSeedResource tests
# ---------------------------------------------------------------------------


class TestDatabaseSeedResource:
    def test_check_returns_verified_by_default(self, db_session):
        res = DatabaseSeedResource(name="test_seed", desired_version="1")
        result = res.check(db_session)
        assert result.status == ResourceStatus.VERIFIED

    def test_custom_check_fn(self, db_session):
        def check(db):
            return ResourceResult(
                resource_name="test_seed",
                resource_type=ResourceType.DATABASE_SEED,
                desired_version="1",
                status=ResourceStatus.DRIFTED,
            )

        res = DatabaseSeedResource(name="test_seed", desired_version="1", check_fn=check)
        result = res.check(db_session)
        assert result.status == ResourceStatus.DRIFTED

    def test_no_db_session_fails(self):
        res = DatabaseSeedResource(name="test_seed", desired_version="1")
        result = res.check(None)
        assert result.status == ResourceStatus.FAILED


# ---------------------------------------------------------------------------
# FeatureFlagResource tests
# ---------------------------------------------------------------------------


class TestFeatureFlagResource:
    def test_condition_met_enables_feature(self, db_session):
        res = FeatureFlagResource(
            name="flag_test",
            flag_name="test_feature",
            condition_fn=lambda db: True,
        )
        result = res.apply(db_session)
        assert result.status == ResourceStatus.VERIFIED
        assert is_feature_enabled("test_feature")

    def test_condition_not_met_disables_feature(self, db_session):
        res = FeatureFlagResource(
            name="flag_test",
            flag_name="test_feature",
            condition_fn=lambda db: False,
            disable_reason="Missing config",
        )
        result = res.apply(db_session)
        assert not is_feature_enabled("test_feature")
        assert result.feature_disabled == "test_feature"


# ---------------------------------------------------------------------------
# StateStore tests
# ---------------------------------------------------------------------------


class TestStateStore:
    def test_upsert_and_get(self, db_session):
        store = StateStore(db_session)
        store.upsert(
            resource_name="test_res",
            resource_type="directory",
            desired_version="1",
            status="verified",
        )
        row = store.get("test_res")
        assert row is not None
        assert row.status == "verified"

    def test_upsert_updates_existing(self, db_session):
        store = StateStore(db_session)
        store.upsert(
            resource_name="test_res",
            resource_type="directory",
            desired_version="1",
            status="drifted",
        )
        store.upsert(
            resource_name="test_res",
            resource_type="directory",
            desired_version="2",
            status="verified",
        )
        row = store.get("test_res")
        assert row.desired_version == "2"
        assert row.status == "verified"


# ---------------------------------------------------------------------------
# Lock tests
# ---------------------------------------------------------------------------


class TestTableBasedLock:
    def test_acquire_and_release(self, db_engine):
        lock = TableBasedLock(db_engine)
        assert lock.acquire("test_lock", timeout=5)
        assert lock.is_held("test_lock")
        lock.release("test_lock")
        assert not lock.is_held("test_lock")

    def test_create_lock_provider_sqlite(self, db_engine):
        provider = create_lock_provider(db_engine)
        assert isinstance(provider, TableBasedLock)


# ---------------------------------------------------------------------------
# Runner integration tests
# ---------------------------------------------------------------------------


class TestDesiredStateRunner:
    def test_full_cycle_with_directory(self, db_engine, db_session, tmp_dir):
        target = tmp_dir / "new_dir"
        resources = [DirectoryResource(name="test", path=target)]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.NORMAL,
        )
        report = runner.run()
        assert report.success
        assert target.is_dir()
        assert report.results[0].status == ResourceStatus.VERIFIED

    def test_dry_run_does_not_modify(self, db_engine, db_session, tmp_dir):
        target = tmp_dir / "should_not_exist"
        resources = [DirectoryResource(name="test", path=target)]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.DRY_RUN,
        )
        report = runner.run()
        assert not target.exists()
        assert report.results[0].status == ResourceStatus.DRIFTED

    def test_check_only_does_not_modify(self, db_engine, db_session, tmp_dir):
        target = tmp_dir / "should_not_exist"
        resources = [DirectoryResource(name="test", path=target)]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.CHECK_ONLY,
        )
        runner.run()
        assert not target.exists()

    def test_critical_failure_marks_report_failed(self, db_engine, db_session, tmp_dir):
        # A file that's not a directory
        file_path = tmp_dir / "blocker"
        file_path.write_text("x")
        resources = [DirectoryResource(name="test", path=file_path, critical=True)]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.NORMAL,
        )
        report = runner.run()
        assert not report.success
        assert report.critical_failures == 1

    def test_non_critical_failure_is_warning(self, db_engine, db_session, tmp_dir):
        file_path = tmp_dir / "blocker"
        file_path.write_text("x")
        resources = [
            DirectoryResource(
                name="test",
                path=file_path,
                critical=False,
                failure_action=FailureAction.WARN_ONLY,
            )
        ]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.NORMAL,
        )
        report = runner.run()
        assert report.success
        assert report.warnings == 1

    def test_idempotent_triple_run(self, db_engine, db_session, tmp_dir):
        target = tmp_dir / "idem_dir"
        resources = [DirectoryResource(name="test", path=target)]
        for _ in range(3):
            runner = DesiredStateRunner(
                resources=resources,
                engine=db_engine,
                db=db_session,
                mode=RunMode.NORMAL,
            )
            report = runner.run()
            assert report.success
        assert target.is_dir()

    def test_report_output_formats(self, db_engine, db_session, tmp_dir):
        resources = [DirectoryResource(name="test", path=tmp_dir)]
        runner = DesiredStateRunner(
            resources=resources,
            engine=db_engine,
            db=db_session,
            mode=RunMode.NORMAL,
        )
        report = runner.run()
        # JSON format
        json_out = report.to_dict()
        assert len(json_out) == 1
        assert json_out[0]["resource_name"] == "test"
        # Text format
        text_out = report.summary_text()
        assert "Reconciliation Report" in text_out
