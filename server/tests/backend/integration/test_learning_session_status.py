"""Test GET /sessions/{id}/status for reconnection decisions.

Covers:
- Endpoint signature and registration
- Returns 'idle' when no learning-tutor AITask exists
- Returns task status (running/completed/failed) when a task exists
- Validates session ownership (raises 404 for cross-child access)
- All IDs serialized as strings (Snowflake convention)
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Signature / registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_endpoint_signature():
    """get_session_status should exist and be an async endpoint."""
    import inspect

    from apps.backend.app.routers.learning_child import get_session_status

    assert inspect.iscoroutinefunction(get_session_status)


def test_status_endpoint_registered_on_router():
    """The /sessions/{session_id}/status route should be registered."""
    from apps.backend.app.routers.learning_child import router

    routes = [r.path for r in router.routes]
    assert "/child/learning/sessions/{session_id}/status" in routes


# ---------------------------------------------------------------------------
# Unit tests with mocked DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_idle_when_no_task():
    """When no learning-tutor AITask exists for the family, status should be 'idle'."""
    from apps.backend.app.routers.learning_child import get_session_status

    fake_session = MagicMock()
    fake_session.thread_id = "42"
    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    # session_service.get_session returns the session
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = fake_session

        # AITask query returns empty list (no task)
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = []
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        result = await get_session_status(session_id=42, db=db, child=fake_child)

    assert result["session_id"] == "42"
    assert result["run_status"] == "idle"
    assert result["thread_id"] == "42"
    assert "task_id" not in result


@pytest.mark.asyncio
async def test_status_returns_running_when_task_active():
    """When a running learning-tutor AITask exists, status should be 'running'."""
    from apps.backend.app.routers.learning_child import get_session_status

    fake_task = MagicMock()
    fake_task.id = 999888777666
    fake_task.status = "running"
    fake_task.progress = {"learning_session_id": "42"}
    fake_task.lease_expires_at = None  # lease not expired

    fake_session = MagicMock()
    fake_session.thread_id = "42"

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = fake_session

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = [fake_task]
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        result = await get_session_status(session_id=42, db=db, child=fake_child)

    assert result["session_id"] == "42"
    assert result["run_status"] == "running"
    assert result["thread_id"] == "42"
    # Snowflake ID must be serialized as string
    assert result["task_id"] == "999888777666"
    assert isinstance(result["task_id"], str)


@pytest.mark.asyncio
async def test_status_returns_completed():
    """When the latest task is completed, status should be 'completed'."""
    from apps.backend.app.routers.learning_child import get_session_status

    fake_task = MagicMock()
    fake_task.id = 123456
    fake_task.status = "completed"
    fake_task.progress = {"learning_session_id": "42"}

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = MagicMock()

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = [fake_task]
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        result = await get_session_status(session_id=42, db=db, child=fake_child)

    assert result["run_status"] == "completed"


@pytest.mark.asyncio
async def test_status_returns_failed():
    """When the latest task has failed, status should be 'failed'."""
    from apps.backend.app.routers.learning_child import get_session_status

    fake_task = MagicMock()
    fake_task.id = 111222
    fake_task.status = "failed"
    fake_task.progress = {"learning_session_id": "42"}

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = MagicMock()

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = [fake_task]
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        result = await get_session_status(session_id=42, db=db, child=fake_child)

    assert result["run_status"] == "failed"


@pytest.mark.asyncio
async def test_status_returns_interrupted_when_lease_expired():
    """When a running task's lease has expired, status should be 'interrupted'."""
    from datetime import UTC, datetime, timedelta

    from apps.backend.app.routers.learning_child import get_session_status

    fake_task = MagicMock()
    fake_task.id = 555666
    fake_task.status = "running"
    fake_task.progress = {"learning_session_id": "42"}
    # Lease expired 5 minutes ago → dead worker
    fake_task.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = MagicMock()

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = [fake_task]
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        result = await get_session_status(session_id=42, db=db, child=fake_child)

    assert result["run_status"] == "interrupted"


@pytest.mark.asyncio
async def test_status_validates_session_ownership():
    """get_session should be called with child.id to enforce ownership."""
    from apps.backend.app.errors import AppError, ErrorCode
    from apps.backend.app.routers.learning_child import get_session_status

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        # Simulate session not found / not owned
        mock_session_svc.get_session.side_effect = AppError(
            ErrorCode.LEARNING_SESSION_NOT_FOUND
        )

        with pytest.raises(AppError) as exc_info:
            await get_session_status(session_id=999, db=db, child=fake_child)

        assert exc_info.value.code == ErrorCode.LEARNING_SESSION_NOT_FOUND
        # Verify get_session was called with correct child_id
        mock_session_svc.get_session.assert_called_once_with(db, 999, 7)


@pytest.mark.asyncio
async def test_status_session_id_serialized_as_string():
    """session_id in response must be a string (Snowflake ID convention)."""
    from apps.backend.app.routers.learning_child import get_session_status

    fake_child = MagicMock()
    fake_child.id = 7
    fake_child.family_id = 100

    db = MagicMock()
    with patch(
        "apps.backend.app.routers.learning_child.session_service"
    ) as mock_session_svc:
        mock_session_svc.get_session.return_value = MagicMock()

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.first.return_value = None
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        # Use a large Snowflake-like ID
        result = await get_session_status(
            session_id=999999999999999, db=db, child=fake_child
        )

    assert isinstance(result["session_id"], str)
    assert result["session_id"] == "999999999999999"
