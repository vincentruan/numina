"""Tests for the ScheduledTask model backing user-configured AI schedules.

Covers the persistence contract the CRUD API and the polling job rely on:
snowflake primary key, family scoping, the enable/poll composite indexes, and
the status lifecycle fields that survive scheduler restarts.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from packages.db.models.scheduled_task import ScheduledTask

_NEXT_RUN = datetime(2026, 11, 4, 1, 0, tzinfo=UTC)  # 09:00 Asia/Shanghai


def _make(**overrides) -> ScheduledTask:
    fields = {
        "family_id": 1001,
        "skill_id": "asset-report",
        "cron_expression": "0 9 * * *",
        "next_run_at": _NEXT_RUN,
    }
    fields.update(overrides)
    return ScheduledTask(**fields)


class TestScheduledTask:
    def test_defaults_for_new_task(self, packages_db):
        task = _make()

        packages_db.add(task)
        packages_db.flush()

        assert task.id is not None
        assert task.is_enabled is True
        assert task.status == "idle"
        assert task.last_run_at is None
        assert task.last_error is None

    def test_persists_schedule_and_failure_detail(self, packages_db):
        packages_db.add(
            _make(
                is_enabled=False,
                status="failed",
                last_run_at=datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
                last_error="agent 执行超时",
            )
        )
        packages_db.flush()

        row = packages_db.query(ScheduledTask).filter_by(family_id=1001).one()
        assert row.skill_id == "asset-report"
        assert row.cron_expression == "0 9 * * *"
        assert row.is_enabled is False
        assert row.status == "failed"
        assert row.last_error == "agent 执行超时"
        assert row.next_run_at == _NEXT_RUN
        assert row.next_run_at.tzinfo is not None

    def test_query_by_family_and_enabled(self, packages_db):
        packages_db.add_all(
            [
                _make(),
                _make(is_enabled=False),
                _make(family_id=2002),
            ]
        )
        packages_db.flush()

        enabled = (
            packages_db.query(ScheduledTask)
            .filter_by(family_id=1001, is_enabled=True)
            .all()
        )
        assert len(enabled) == 1
        assert enabled[0].family_id == 1001

    def test_query_due_tasks_excludes_future_and_disabled(self, packages_db):
        packages_db.add_all(
            [
                _make(next_run_at=datetime(2026, 11, 3, 0, 0, tzinfo=UTC)),
                _make(next_run_at=datetime(2026, 11, 5, 0, 0, tzinfo=UTC)),
                _make(
                    is_enabled=False,
                    next_run_at=datetime(2026, 11, 3, 0, 0, tzinfo=UTC),
                ),
            ]
        )
        packages_db.flush()

        now = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)
        due = (
            packages_db.query(ScheduledTask)
            .filter(
                ScheduledTask.is_enabled.is_(True),
                ScheduledTask.next_run_at <= now,
                ScheduledTask.status != "running",
            )
            .all()
        )
        assert len(due) == 1
        assert due[0].is_enabled is True

    def test_family_id_is_required(self, packages_db):
        packages_db.add(_make(family_id=None))

        with pytest.raises(IntegrityError):
            packages_db.flush()

    def test_snowflake_id_is_unique_per_row(self, packages_db):
        packages_db.add_all([_make(), _make(cron_expression="0 10 * * *")])
        packages_db.flush()

        ids = [t.id for t in packages_db.query(ScheduledTask).all()]
        assert len(ids) == len(set(ids))

    def test_declares_family_and_poll_indexes(self):
        table = ScheduledTask.__table__
        index_columns = {
            index.name: [col.name for col in index.columns] for index in table.indexes
        }

        assert index_columns["ix_scheduled_tasks_family_enabled"] == [
            "family_id",
            "is_enabled",
        ]
        assert index_columns["ix_scheduled_tasks_poll"] == [
            "is_enabled",
            "next_run_at",
        ]
