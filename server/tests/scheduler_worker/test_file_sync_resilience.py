"""file_sync_job resilience behaviours for issue #158.

Covers the four silent-failure fixes:
1. Decryption failure is logged at CRITICAL with actionable context (not a bare warning).
2. Path mismatch is diagnosed with UPLOAD_DIR + local_path in the log.
3. A rate limit does not consume a file's retry budget and stops the batch.
4. Transient failures auto-recover after FILE_SYNC_FAILED_RECOVERY_HOURS,
   while permanent failures (oversized) never auto-recover.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.settings import settings
from packages.storage.base import StorageFileSizeError, StorageRateLimitError

BACKEND_ID = 11
FAMILY_ID = 7


def _backend_row() -> SimpleNamespace:
    return SimpleNamespace(
        id=BACKEND_ID,
        family_id=FAMILY_ID,
        backend_type="github",
        config="enc:cfg",
        is_active=True,
        last_synced_at=None,
    )


def _loc(file_id: int = 101, retry_count: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        file_id=file_id,
        backend_id=BACKEND_ID,
        sync_status="pending",
        remote_path=None,
        remote_url=None,
        synced_at=None,
        last_error=None,
        retry_count=retry_count,
    )


def _cached_file(file_id: int, local_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=file_id, local_path=local_path, date_dir="20260101", deleted_at=None
    )


def _configure_db(mock_session, *, backends, pending, cached_files, recovered=0):
    """Wire db.query() for the three/four query shapes file_sync_job issues."""

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", "")
        if name == "StorageBackend":
            q.filter_by.return_value.all.return_value = backends
        elif name == "FileRemoteLocation":
            # Self-referential chain: N calls to .filter() all return the same
            # mock, so the query stays valid however many filters the job adds.
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.limit.return_value.all.return_value = pending
            chain.update.return_value = recovered
            q.filter_by.return_value = chain
        elif name == "CachedFile":
            q.filter.return_value.all.return_value = cached_files
        return q

    mock_session.query.side_effect = query_side_effect


@pytest.fixture
def mock_session_local():
    session = MagicMock()
    session.close = MagicMock()
    with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=session):
        yield session


@pytest.fixture
def no_sleep():
    with patch(
        "apps.scheduler_worker.jobs.asyncio.sleep", new=AsyncMock()
    ) as sleep, patch("apps.scheduler_worker.jobs.random.uniform", return_value=0.0):
        yield sleep


@pytest.fixture
def backend():
    b = MagicMock()
    b.save = AsyncMock(return_value="20260101/f.png")
    b.get_url = MagicMock(return_value="https://example/f.png")
    b.write_delay_range = (0.0, 0.0)
    return b


class TestDecryptFailureIsLoud:
    async def test_logs_critical_with_family_and_backend_context(
        self, mock_session_local, no_sleep, caplog
    ):
        _configure_db(mock_session_local, backends=[_backend_row()], pending=[], cached_files=[])

        with patch("packages.storage.config_crypto.decrypt_config", return_value=None), caplog.at_level(
            "CRITICAL", logger="apps.scheduler_worker.jobs"
        ):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        critical = [r for r in caplog.records if r.levelname == "CRITICAL"]
        assert critical, "decryption failure must be CRITICAL, not a silent warning"
        message = critical[0].getMessage()
        assert str(FAMILY_ID) in message
        assert str(BACKEND_ID) in message
        assert "STORAGE_ENCRYPTION_KEY" in message

    async def test_still_skips_the_backend(self, mock_session_local, no_sleep, caplog, backend):
        _configure_db(mock_session_local, backends=[_backend_row()], pending=[_loc()], cached_files=[])

        with patch("packages.storage.config_crypto.decrypt_config", return_value=None), patch(
            "packages.storage.factory.get_backend_for_type", return_value=backend
        ) as factory, caplog.at_level("CRITICAL", logger="apps.scheduler_worker.jobs"):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        factory.assert_not_called()
        backend.save.assert_not_called()


class TestPathMismatchDiagnostics:
    async def test_logs_upload_dir_and_local_path_on_mismatch(
        self, mock_session_local, no_sleep, tmp_path, backend, caplog
    ):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        outside = tmp_path / "elsewhere" / "f.png"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b"data")

        loc = _loc()
        _configure_db(
            mock_session_local,
            backends=[_backend_row()],
            pending=[loc],
            cached_files=[_cached_file(101, str(outside))],
        )

        with patch.object(settings, "UPLOAD_DIR", str(upload_dir)), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend), caplog.at_level(
            "WARNING", logger="apps.scheduler_worker.jobs"
        ):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "failed"
        assert "路径越界" in loc.last_error

        messages = " ".join(r.getMessage() for r in caplog.records)
        assert str(upload_dir) in messages
        assert str(outside) in messages

    async def test_summarises_mismatch_count_per_backend(
        self, mock_session_local, no_sleep, tmp_path, backend, caplog
    ):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        outside = tmp_path / "out" / "f.png"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b"data")

        _configure_db(
            mock_session_local,
            backends=[_backend_row()],
            pending=[_loc(101), _loc(102)],
            cached_files=[_cached_file(101, str(outside)), _cached_file(102, str(outside))],
        )

        with patch.object(settings, "UPLOAD_DIR", str(upload_dir)), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend), caplog.at_level(
            "ERROR", logger="apps.scheduler_worker.jobs"
        ):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        errors = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert any("2" in m and "路径越界" in m for m in errors)


class TestRateLimitDoesNotBurnRetries:
    async def test_rate_limit_keeps_retry_count(
        self, mock_session_local, no_sleep, tmp_path, backend
    ):
        target = tmp_path / "uploads" / "f.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"data")

        loc = _loc(retry_count=1)
        _configure_db(
            mock_session_local,
            backends=[_backend_row()],
            pending=[loc],
            cached_files=[_cached_file(101, str(target))],
        )
        backend.save = AsyncMock(side_effect=StorageRateLimitError(reset_at=1_700_000_000))

        with patch.object(settings, "UPLOAD_DIR", str(tmp_path / "uploads")), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.retry_count == 1, "a rate limit is not the file's fault"
        assert loc.sync_status == "pending"
        assert "速率限制" in loc.last_error

    async def test_rate_limit_stops_remaining_batch(
        self, mock_session_local, no_sleep, tmp_path, backend
    ):
        upload_dir = tmp_path / "uploads"
        files = []
        locations = []
        for i in range(3):
            target = upload_dir / f"f{i}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"data")
            files.append(_cached_file(101 + i, str(target)))
            locations.append(_loc(file_id=101 + i))

        _configure_db(
            mock_session_local, backends=[_backend_row()], pending=locations, cached_files=files
        )
        backend.save = AsyncMock(side_effect=StorageRateLimitError(reset_at=1_700_000_000))

        with patch.object(settings, "UPLOAD_DIR", str(upload_dir)), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert backend.save.await_count == 1, "stop hammering a rate-limited backend"
        # Remaining files are untouched, ready for the next cycle.
        assert locations[1].retry_count == 0
        assert locations[2].retry_count == 0


class TestOversizedFileIsPermanent:
    async def test_oversized_file_marked_failed_without_retry_budget(
        self, mock_session_local, no_sleep, tmp_path, backend
    ):
        from apps.scheduler_worker.jobs import _PERMANENT_FAILURE_RETRY

        target = tmp_path / "uploads" / "big.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"data")

        loc = _loc()
        _configure_db(
            mock_session_local,
            backends=[_backend_row()],
            pending=[loc],
            cached_files=[_cached_file(101, str(target))],
        )
        backend.save = AsyncMock(
            side_effect=StorageFileSizeError(
                "too large", file_size=2_000_000, max_size=750 * 1024
            )
        )

        with patch.object(settings, "UPLOAD_DIR", str(tmp_path / "uploads")), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "failed"
        assert loc.retry_count == _PERMANENT_FAILURE_RETRY
        assert "too large" in loc.last_error
        assert backend.save.await_count == 1, "an oversized file must not be retried"


class TestAutoRecovery:
    async def test_recovery_count_is_logged(self, mock_session_local, no_sleep, caplog, backend):
        _configure_db(
            mock_session_local, backends=[_backend_row()], pending=[], cached_files=[], recovered=4
        )
        with patch("packages.storage.config_crypto.decrypt_config", return_value={}), patch(
            "packages.storage.factory.get_backend_for_type", return_value=backend
        ), caplog.at_level("INFO", logger="apps.scheduler_worker.jobs"):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        info = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("自动恢复" in m and "4" in m for m in info)
        mock_session_local.commit.assert_called()

    def test_recovery_window_is_configurable(self):
        assert settings.FILE_SYNC_FAILED_RECOVERY_HOURS > 0


class TestSuccessfulSyncClearsPriorError:
    async def test_success_resets_retry_and_error(
        self, mock_session_local, no_sleep, tmp_path, backend
    ):
        target = tmp_path / "uploads" / "f.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"data")

        loc = _loc(retry_count=2)
        loc.last_error = "previous failure"
        _configure_db(
            mock_session_local,
            backends=[_backend_row()],
            pending=[loc],
            cached_files=[_cached_file(101, str(target))],
        )

        with patch.object(settings, "UPLOAD_DIR", str(tmp_path / "uploads")), patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ), patch("packages.storage.factory.get_backend_for_type", return_value=backend):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "synced"
        assert loc.retry_count == 0
        assert loc.last_error is None


# ════════════════════════════════════════════════════════════════════════════
# _requeue_stale_failures — real DB semantics (SQLAlchemy in-memory SQLite)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def recovery_db():
    """Isolated in-memory DB with the tables _requeue_stale_failures touches."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import packages.db.models.cached_file  # noqa: F401  (register tables)
    import packages.db.models.file_remote_location  # noqa: F401
    import packages.db.models.storage_backend  # noqa: F401
    from packages.db.session import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session, datetime, timedelta, UTC
    finally:
        session.close()
        engine.dispose()


def _insert_loc(db, *, backend_id, file_id, status, retry_count, updated_at):
    from packages.db.models.file_remote_location import FileRemoteLocation

    loc = FileRemoteLocation(
        file_id=file_id,
        backend_id=backend_id,
        sync_status=status,
        retry_count=retry_count,
        updated_at=updated_at,
    )
    db.add(loc)
    db.commit()
    return loc


class TestRequeueStaleFailures:
    """The auto-recovery sweep, exercised against a real database."""

    def _now(self, datetime, UTC):
        return datetime.now(UTC)

    def test_requeues_transient_failure_past_the_window(
        self, recovery_db, monkeypatch
    ):
        from apps.scheduler_worker.jobs import _requeue_stale_failures

        db, datetime, timedelta, UTC = recovery_db
        old = datetime.now(UTC) - timedelta(hours=48)
        loc = _insert_loc(
            db, backend_id=1, file_id=1, status="failed", retry_count=3, updated_at=old
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 1
        db.commit()
        db.refresh(loc)

        assert loc.sync_status == "pending"
        assert loc.retry_count == 0

    def test_keeps_recent_failures(self, recovery_db, monkeypatch):
        from apps.scheduler_worker.jobs import _requeue_stale_failures

        db, datetime, timedelta, UTC = recovery_db
        recent = datetime.now(UTC) - timedelta(hours=1)
        loc = _insert_loc(
            db, backend_id=1, file_id=2, status="failed", retry_count=3, updated_at=recent
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 0
        db.refresh(loc)
        assert loc.sync_status == "failed"

    def test_never_requeues_permanent_failures(self, recovery_db, monkeypatch):
        """An oversized file can never succeed — re-queueing it would loop forever."""
        from apps.scheduler_worker.jobs import (
            _PERMANENT_FAILURE_RETRY,
            _requeue_stale_failures,
        )

        db, datetime, timedelta, UTC = recovery_db
        old = datetime.now(UTC) - timedelta(days=365)
        loc = _insert_loc(
            db,
            backend_id=1,
            file_id=3,
            status="failed",
            retry_count=_PERMANENT_FAILURE_RETRY,
            updated_at=old,
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 0
        db.refresh(loc)
        assert loc.sync_status == "failed"
        assert loc.retry_count == _PERMANENT_FAILURE_RETRY

    def test_ignores_rows_below_the_retry_budget(self, recovery_db, monkeypatch):
        from apps.scheduler_worker.jobs import _requeue_stale_failures

        db, datetime, timedelta, UTC = recovery_db
        old = datetime.now(UTC) - timedelta(hours=48)
        loc = _insert_loc(
            db, backend_id=1, file_id=4, status="failed", retry_count=1, updated_at=old
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 0
        db.refresh(loc)
        assert loc.sync_status == "failed"

    def test_ignores_other_backends(self, recovery_db, monkeypatch):
        from apps.scheduler_worker.jobs import _requeue_stale_failures

        db, datetime, timedelta, UTC = recovery_db
        old = datetime.now(UTC) - timedelta(hours=48)
        other = _insert_loc(
            db, backend_id=99, file_id=5, status="failed", retry_count=3, updated_at=old
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 0
        db.refresh(other)
        assert other.sync_status == "failed"

    def test_ignores_synced_rows(self, recovery_db, monkeypatch):
        from apps.scheduler_worker.jobs import _requeue_stale_failures

        db, datetime, timedelta, UTC = recovery_db
        old = datetime.now(UTC) - timedelta(hours=48)
        loc = _insert_loc(
            db, backend_id=1, file_id=6, status="synced", retry_count=3, updated_at=old
        )

        monkeypatch.setattr(settings, "FILE_SYNC_FAILED_RECOVERY_HOURS", 24)
        assert _requeue_stale_failures(db, 1) == 0
        db.refresh(loc)
        assert loc.sync_status == "synced"
