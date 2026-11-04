"""Tests for scheduled_task_poll_job.

The poll job decides, once a minute, which tasks fire. These tests pin the
properties that make that safe: a task that is not due is left alone, a task
that fails does not become permanently due, and a task whose process died is
recovered instead of staying stuck.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import apps.scheduler_worker.jobs as jobs_module
from apps.scheduler_worker.jobs import scheduled_task_poll_job
from packages.db.models.scheduled_task import ScheduledTask
from packages.db.session import Base


@pytest.fixture()
def db_session(monkeypatch):
    """Isolated in-memory DB, patched in as the job's session factory.

    The job opens its own session via the module-level SessionLocal, so the job
    must be handed this engine rather than the ambient one.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(jobs_module, "SessionLocal", factory, raising=True)

    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_task(db: Session, **overrides) -> ScheduledTask:
    fields = {
        "family_id": 1001,
        "skill_id": "asset-report",
        "cron_expression": "0 9 * * *",
        "is_enabled": True,
        "next_run_at": datetime.now(UTC) - timedelta(minutes=5),
        "status": "idle",
    }
    fields.update(overrides)
    task = ScheduledTask(**fields)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _mock_client(status_code: int = 200, side_effect=None):
    """Patch httpx.AsyncClient so the job's POST is intercepted."""
    response = AsyncMock()
    response.status_code = status_code
    response.text = ""

    client = AsyncMock()
    client.post = AsyncMock(side_effect=side_effect, return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    return patch("httpx.AsyncClient", return_value=client), client


@pytest.mark.asyncio
async def test_poll_executes_due_task_and_advances_schedule(db_session):
    task = _make_task(db_session)
    patcher, client = _mock_client()

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "success"
    assert task.last_run_at is not None
    assert task.last_error is None
    assert task.next_run_at > datetime.now(UTC)
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_skips_disabled_task(db_session):
    task = _make_task(db_session, is_enabled=False)
    patcher, client = _mock_client()

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "idle"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_skips_future_task(db_session):
    task = _make_task(db_session, next_run_at=datetime.now(UTC) + timedelta(hours=1))
    patcher, client = _mock_client()

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "idle"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_task_does_not_stay_due(db_session):
    """A failure must not leave the row permanently due.

    Without advancing next_run_at the same row is re-dispatched on every poll,
    turning one backend error into a 1-minute retry loop forever.
    """
    task = _make_task(db_session, next_run_at=datetime.now(UTC) - timedelta(minutes=5))
    patcher, _ = _mock_client(side_effect=RuntimeError("Network error"))

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "failed"
    assert task.last_error is not None
    assert "Network error" in task.last_error
    assert task.next_run_at > datetime.now(UTC)

    # A second poll must not re-dispatch it.
    patcher2, client2 = _mock_client()
    with patcher2:
        await scheduled_task_poll_job()
    client2.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_error_marks_failed_and_records_status(db_session):
    task = _make_task(db_session)
    patcher, _ = _mock_client(status_code=500)

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "failed"
    assert task.last_error is not None
    assert "500" in task.last_error
    assert task.next_run_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_unparseable_cron_still_advances_schedule(db_session):
    """A cron that no longer parses must not strand the task as due."""
    task = _make_task(db_session, cron_expression="bogus")
    patcher, _ = _mock_client(status_code=200)

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.next_run_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_poll_resets_stale_running_tasks(db_session):
    task = _make_task(
        db_session,
        status="running",
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        updated_at=datetime.now(UTC) - timedelta(minutes=15),
    )
    patcher, _ = _mock_client()

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "idle"


@pytest.mark.asyncio
async def test_poll_leaves_recent_running_tasks_alone(db_session):
    task = _make_task(
        db_session,
        status="running",
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        updated_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    patcher, _ = _mock_client()

    with patcher:
        await scheduled_task_poll_job()

    db_session.refresh(task)
    assert task.status == "running"


@pytest.mark.asyncio
async def test_poll_skips_task_claimed_by_another_process():
    """The rowcount guard is the only thing preventing duplicate dispatch.

    R7 requires that two overlapping polls never both run the same task. The due
    SELECT and the claiming UPDATE are separate statements, so a task can be
    claimed by a competitor in between; when that happens the UPDATE matches zero
    rows and the job must skip rather than dispatch a second copy.
    """
    from sqlalchemy import event

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    setup = factory()
    task = _make_task(setup)
    task_id = task.id
    setup.close()

    claimed = {"done": False}

    @event.listens_for(engine, "before_cursor_execute")
    def _steal_lock(conn, cursor, statement, parameters, context, executemany):
        """Simulate a competing worker claiming the row just before our UPDATE.

        Only the claim statement (``SET status=? ... WHERE id = ? AND status != ?``)
        is intercepted, so the stale-reset UPDATE is left alone.
        """
        if claimed["done"]:
            return
        if "SET status=?" in statement and "scheduled_tasks.id = ?" in statement:
            claimed["done"] = True
            conn.exec_driver_sql(
                "UPDATE scheduled_tasks SET status='running' WHERE id=?", (task_id,)
            )

    checker = factory()
    caplog_target = jobs_module  # noqa: F841 -- keep the monkeypatch target obvious

    patcher, client = _mock_client()
    try:
        with patch.object(jobs_module, "SessionLocal", factory), patcher:
            await scheduled_task_poll_job()

        assert claimed["done"], "the steal hook never fired; test does not cover the guard"
        # The competitor owns the task, so this process must not dispatch it.
        client.post.assert_not_awaited()

        row = checker.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        assert row.status == "running"
    finally:
        event.remove(engine, "before_cursor_execute", _steal_lock)
        checker.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_schedule_edit_during_dispatch_wins_over_stale_read():
    """next_run_at must be derived from the schedule current at claim time.

    An owner can edit cron_expression while a dispatch is in flight. The poll
    caches the expression from the batch SELECT, so reading it before the claim
    commit would compute next_run_at from the superseded expression and silently
    overwrite the owner's change. Daily -> weekly would then fire once too often;
    weekly -> daily would skip a day.
    """
    from sqlalchemy import event

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    setup = factory()
    task = _make_task(setup, cron_expression="0 9 * * *")
    task_id = task.id
    setup.close()

    edits = {"applied": False}

    @event.listens_for(engine, "before_cursor_execute")
    def _owner_edits_schedule(conn, cursor, statement, parameters, context, executemany):
        """Apply the owner's edit just before the claim commit lands."""
        if edits["applied"]:
            return
        if "SET status=?" in statement and "scheduled_tasks.id = ?" in statement:
            edits["applied"] = True
            conn.exec_driver_sql(
                "UPDATE scheduled_tasks SET cron_expression='30 6 * * 1' WHERE id=?",
                (task_id,),
            )

    patcher, _client = _mock_client()
    checker = factory()
    try:
        with patch.object(jobs_module, "SessionLocal", factory), patcher:
            await scheduled_task_poll_job()

        assert edits["applied"], "the edit hook never fired; test does not cover the read"

        row = checker.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        # The expression is interpreted in Asia/Shanghai and stored as UTC, so the
        # edited "30 6 * * 1" is Monday 06:30 CST == Sunday 22:30 UTC. The superseded
        # "0 9 * * *" would have produced 01:00 UTC on a daily cadence instead.
        local = row.next_run_at.astimezone(ZoneInfo("Asia/Shanghai"))
        assert local.weekday() == 0
        assert (local.hour, local.minute) == (6, 30)
        assert row.next_run_at.utcoffset() is not None
    finally:
        event.remove(engine, "before_cursor_execute", _owner_edits_schedule)
        checker.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
