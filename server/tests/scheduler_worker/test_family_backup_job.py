"""Behaviour of family_backup_job.

The job is the only thing standing between a family and having no recoverable
copy of their data, so these tests pin the properties that make it trustworthy:
one family's failure does not stop the others, a repeated failure becomes
visible rather than silent, and pruning never fails a backup that succeeded.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps.scheduler_worker.jobs import family_backup_job

FAMILY_A = 501
FAMILY_B = 502


def _backend_row(family_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=family_id * 10,
        family_id=family_id,
        backend_type="local",
        config="enc",
        is_active=True,
    )


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def filter_by(self, **k):
        return self

    def order_by(self, *a):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


def _db_with(backends):
    db = SimpleNamespace(
        query=lambda model: _FakeQuery(backends),
        commit=lambda: None,
        rollback=lambda: None,
        close=lambda: None,
    )
    return db


class TestFamilyBackupJob:
    async def test_skips_when_no_family_has_a_backend(self):
        db = _db_with([])
        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "packages.domain.backup.orchestrator.create_backup", new=AsyncMock()
        ) as create:
            await family_backup_job()

        create.assert_not_awaited()

    async def test_backs_up_every_family_with_a_backend(self):
        db = _db_with([_backend_row(FAMILY_A), _backend_row(FAMILY_B)])
        create = AsyncMock(
            return_value=(SimpleNamespace(file_path="p", file_size=1), {})
        )
        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "apps.scheduler_worker.jobs._already_backed_up_today", return_value=False
        ), patch(
            "packages.domain.backup.orchestrator.create_backup", new=create
        ), patch(
            "apps.scheduler_worker.jobs._prune_old_backups", new=AsyncMock()
        ):
            await family_backup_job()

        assert create.await_count == 2
        called = {c.args[1] for c in create.await_args_list}
        assert called == {FAMILY_A, FAMILY_B}

    async def test_one_family_failure_does_not_stop_the_others(self):
        db = _db_with([_backend_row(FAMILY_A), _backend_row(FAMILY_B)])

        async def _create(_db, family_id, *, trigger_type):
            if family_id == FAMILY_A:
                raise RuntimeError("GitHub 认证失败: 401")
            return SimpleNamespace(file_path="ok", file_size=1), {}

        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "apps.scheduler_worker.jobs._already_backed_up_today", return_value=False
        ), patch(
            "packages.domain.backup.orchestrator.create_backup", new=_create
        ), patch(
            "apps.scheduler_worker.jobs._prune_old_backups", new=AsyncMock()
        ), patch(
            "apps.scheduler_worker.jobs._report_failure_streak"
        ) as report:
            await family_backup_job()

        assert report.call_count == 1
        assert report.call_args.args[1] == FAMILY_A

    async def test_prune_runs_only_after_a_successful_backup(self):
        db = _db_with([_backend_row(FAMILY_A)])
        prune = AsyncMock()

        async def _create(_db, family_id, *, trigger_type):
            raise RuntimeError("boom")

        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "packages.domain.backup.orchestrator.create_backup", new=_create
        ), patch(
            "apps.scheduler_worker.jobs._prune_old_backups", new=prune
        ), patch(
            "apps.scheduler_worker.jobs._report_failure_streak"
        ):
            await family_backup_job()

        prune.assert_not_awaited()


class TestPruneOldBackups:
    async def test_prunes_only_beyond_the_retention_count(self):
        from apps.scheduler_worker.jobs import _prune_old_backups

        backend = SimpleNamespace(
            list=AsyncMock(
                return_value=[
                    {"path": "backups/20260101"},
                    {"path": "backups/20260102"},
                    {"path": "backups/20260103"},
                ]
            ),
            delete=AsyncMock(),
        )
        with patch(
            "packages.domain.backup.orchestrator.resolve_backend",
            return_value=backend,
        ), patch(
            "packages.core.settings.settings.BACKUP_RETENTION_COUNT", 1
        ):
            await _prune_old_backups(SimpleNamespace(), FAMILY_A)

        deleted = [c.args[0] for c in backend.delete.await_args_list]
        assert deleted == ["backups/20260101", "backups/20260102"]

    async def test_prune_failure_never_raises(self):
        from apps.scheduler_worker.jobs import _prune_old_backups

        backend = SimpleNamespace(
            list=AsyncMock(side_effect=RuntimeError("network down")),
            delete=AsyncMock(),
        )
        with patch(
            "packages.domain.backup.orchestrator.resolve_backend",
            return_value=backend,
        ):
            await _prune_old_backups(SimpleNamespace(), FAMILY_A)

    async def test_no_deletion_when_under_retention(self):
        from apps.scheduler_worker.jobs import _prune_old_backups

        backend = SimpleNamespace(
            list=AsyncMock(return_value=[{"path": "backups/20260101"}]),
            delete=AsyncMock(),
        )
        with patch(
            "packages.domain.backup.orchestrator.resolve_backend",
            return_value=backend,
        ), patch("packages.core.settings.settings.BACKUP_RETENTION_COUNT", 7):
            await _prune_old_backups(SimpleNamespace(), FAMILY_A)

        backend.delete.assert_not_awaited()


class TestFailureStreak:
    def test_escalates_to_critical_at_three_failures(self):
        from apps.scheduler_worker.jobs import _report_failure_streak

        failed = SimpleNamespace(status="failed", consecutive_failures=3, error_message="401")
        db = _db_with([failed])
        with patch("packages.core.logging.get_logger") as _, patch.object(
            __import__("apps.scheduler_worker.jobs", fromlist=["logger"]),
            "logger",
        ) as log:
            _report_failure_streak(db, FAMILY_A)
            assert log.critical.called

    def test_stays_silent_below_the_threshold(self):
        from apps.scheduler_worker.jobs import _report_failure_streak

        failed = SimpleNamespace(status="failed", consecutive_failures=1, error_message="401")
        db = _db_with([failed])
        with patch.object(
            __import__("apps.scheduler_worker.jobs", fromlist=["logger"]),
            "logger",
        ) as log:
            _report_failure_streak(db, FAMILY_A)
            log.critical.assert_not_called()

    def test_stays_silent_after_a_success(self):
        from apps.scheduler_worker.jobs import _report_failure_streak

        ok = SimpleNamespace(status="success", consecutive_failures=0, error_message=None)
        db = _db_with([ok])
        with patch.object(
            __import__("apps.scheduler_worker.jobs", fromlist=["logger"]),
            "logger",
        ) as log:
            _report_failure_streak(db, FAMILY_A)
            log.critical.assert_not_called()


class TestIdempotency:
    async def test_skips_a_family_already_backed_up_today(self):
        db = _db_with([_backend_row(FAMILY_A)])
        create = AsyncMock()
        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "apps.scheduler_worker.jobs._already_backed_up_today", return_value=True
        ), patch(
            "packages.domain.backup.orchestrator.create_backup", new=create
        ):
            await family_backup_job()

        create.assert_not_awaited()

    async def test_runs_when_today_has_no_successful_backup(self):
        db = _db_with([_backend_row(FAMILY_A)])
        create = AsyncMock(
            return_value=(SimpleNamespace(file_path="p", file_size=1), {})
        )
        with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=db), patch(
            "apps.scheduler_worker.jobs._already_backed_up_today", return_value=False
        ), patch(
            "packages.domain.backup.orchestrator.create_backup", new=create
        ), patch(
            "apps.scheduler_worker.jobs._prune_old_backups", new=AsyncMock()
        ):
            await family_backup_job()

        assert create.await_count == 1
