"""Tests for scheduled_task_poll_job.

Covers the polling contract: queries due tasks, updates status, calls backend,
handles failures, resets stale running tasks.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from apps.scheduler_worker.jobs import scheduled_task_poll_job
from packages.db.models.scheduled_task import ScheduledTask


@pytest.fixture
def db_session():
    """Yield a test database session."""
    from packages.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_task(db_session):
    """Create a sample scheduled task due now."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        status="idle",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    yield task
    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()


@pytest.mark.asyncio
async def test_poll_finds_and_executes_due_task(db_session, sample_task):
    """Poll job should find a due task and execute it."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await scheduled_task_poll_job()

    # Task should be updated to 'success'
    db_session.refresh(sample_task)
    assert sample_task.status == "success"
    assert sample_task.last_run_at is not None
    assert sample_task.last_error is None
    # next_run_at should be advanced
    assert sample_task.next_run_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_poll_skips_disabled_task(db_session):
    """Poll job should skip disabled tasks."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=False,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        status="idle",
    )
    db_session.add(task)
    db_session.commit()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await scheduled_task_poll_job()

    # Task should remain idle
    db_session.refresh(task)
    assert task.status == "idle"
    # No HTTP call should have been made
    mock_client.post.assert_not_called()

    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()


@pytest.mark.asyncio
async def test_poll_skips_future_task(db_session):
    """Poll job should skip tasks scheduled in the future."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        status="idle",
    )
    db_session.add(task)
    db_session.commit()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await scheduled_task_poll_job()

    # Task should remain idle
    db_session.refresh(task)
    assert task.status == "idle"
    mock_client.post.assert_not_called()

    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()


@pytest.mark.asyncio
async def test_poll_handles_failure(db_session):
    """Poll job should mark task as 'failed' on error."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        status="idle",
    )
    db_session.add(task)
    db_session.commit()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        # Make __aexit__ not suppress exceptions
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value = mock_client

        await scheduled_task_poll_job()

    # Task should be marked as failed
    db_session.refresh(task)
    assert task.status == "failed"
    assert task.last_error is not None
    assert "Network error" in task.last_error

    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()


@pytest.mark.asyncio
async def test_poll_resets_stale_running_tasks(db_session):
    """Poll job should reset tasks stuck in 'running' for > 10 minutes."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        status="running",
        updated_at=datetime.now(UTC) - timedelta(minutes=15),
    )
    db_session.add(task)
    db_session.commit()

    await scheduled_task_poll_job()

    # Task should be reset to idle
    db_session.refresh(task)
    assert task.status == "idle"

    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()


@pytest.mark.asyncio
async def test_poll_does_not_reset_recent_running_tasks(db_session):
    """Poll job should not reset tasks that started running recently."""
    task = ScheduledTask(
        family_id=1001,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        status="running",
        updated_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(task)
    db_session.commit()

    await scheduled_task_poll_job()

    # Task should still be running
    db_session.refresh(task)
    assert task.status == "running"

    # Cleanup
    db_session.query(ScheduledTask).filter(ScheduledTask.id == task.id).delete()
    db_session.commit()
