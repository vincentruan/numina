"""Tests for scheduled_task_poll_job.

The poll job decides, once a minute, which tasks fire. These tests pin the
properties that make that safe: a task that is not due is left alone, a task
that fails does not become permanently due, and a task whose process died is
recovered instead of staying stuck.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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
