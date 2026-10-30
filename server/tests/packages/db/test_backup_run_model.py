"""Tests for the BackupRun model backing family backup history.

Covers the persistence contract the backup job and the backup-listing
endpoint rely on: snowflake primary key, family scoping, the consecutive
failure counter that survives scheduler restarts, and trigger provenance.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from packages.db.models.backup_run import BackupRun


def _make(**overrides) -> BackupRun:
    fields = {
        "family_id": 1001,
        "backup_date": "20261030",
        "file_path": "backups/20261030/143000/numina_backup_1001.json",
        "file_size": 4096,
        "status": "success",
        "trigger_type": "scheduled",
    }
    fields.update(overrides)
    return BackupRun(**fields)


class TestBackupRun:
    def test_counts_consecutive_failures_from_zero(self, packages_db):
        run = _make(status="success", trigger_type="manual")

        packages_db.add(run)
        packages_db.flush()

        assert run.consecutive_failures == 0
        assert run.id is not None

    def test_persists_failure_detail(self, packages_db):
        packages_db.add(
            _make(
                status="failed",
                error_message="GitHub 认证失败: 401",
                consecutive_failures=2,
                file_size=None,
            )
        )
        packages_db.flush()

        row = packages_db.query(BackupRun).filter_by(family_id=1001).one()
        assert row.status == "failed"
        assert row.error_message == "GitHub 认证失败: 401"
        assert row.consecutive_failures == 2
        assert row.file_size is None

    def test_query_by_family_and_trigger(self, packages_db):
        packages_db.add_all(
            [
                _make(trigger_type="scheduled"),
                _make(trigger_type="manual", backup_date="20261031"),
                _make(family_id=2002, backup_date="20261031"),
            ]
        )
        packages_db.flush()

        manual = (
            packages_db.query(BackupRun)
            .filter_by(family_id=1001, trigger_type="manual")
            .all()
        )
        assert len(manual) == 1
        assert manual[0].backup_date == "20261031"

    def test_family_id_is_required(self, packages_db):
        packages_db.add(_make(family_id=None))

        with pytest.raises(IntegrityError):
            packages_db.flush()

    def test_snowflake_id_is_unique_per_row(self, packages_db):
        packages_db.add_all([_make(), _make(backup_date="20261031")])
        packages_db.flush()

        ids = [r.id for r in packages_db.query(BackupRun).all()]
        assert len(ids) == len(set(ids))
