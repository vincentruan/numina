"""Test the assessment streaming endpoint and session service helpers."""

import pytest


def test_get_thread_id_for_session():
    """str(session.id) should be passed to agent as thread_id."""
    from apps.backend.app.services.learning.session_service import (
        get_thread_id_for_session,
    )

    assert get_thread_id_for_session(12345) == "12345"
    assert get_thread_id_for_session(999999999999999) == "999999999999999"
    assert get_thread_id_for_session(1) == "1"


def test_get_session_validates_ownership():
    """get_session should raise when session doesn't belong to child."""
    from unittest.mock import MagicMock

    from apps.backend.app.errors import AppError, ErrorCode
    from apps.backend.app.services.learning.session_service import get_session

    db = MagicMock()
    # Query returns None => session not found / not owned
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock

    with pytest.raises(AppError) as exc_info:
        get_session(db, session_id=1, child_id=999)

    assert exc_info.value.code == ErrorCode.LEARNING_SESSION_NOT_FOUND


def test_get_session_returns_session():
    """get_session should return the session when found and owned."""
    from unittest.mock import MagicMock

    from apps.backend.app.services.learning.session_service import get_session

    fake_session = MagicMock()
    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = fake_session
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock

    result = get_session(db, session_id=42, child_id=7)
    assert result is fake_session


@pytest.mark.asyncio
async def test_assess_stream_endpoint_signature():
    """The stream_assessment function should exist and be an async endpoint."""
    import inspect

    from apps.backend.app.routers.learning_child import stream_assessment

    assert inspect.iscoroutinefunction(stream_assessment)


@pytest.mark.asyncio
async def test_history_endpoint_signature():
    """The get_session_history function should exist and be an async endpoint."""
    import inspect

    from apps.backend.app.routers.learning_child import get_session_history

    assert inspect.iscoroutinefunction(get_session_history)


def test_assess_stream_request_model():
    """AssessStreamRequest should accept optional user_message."""
    from apps.backend.app.routers.learning_child import AssessStreamRequest

    # No body
    empty = AssessStreamRequest()
    assert empty.user_message is None

    # With message
    with_msg = AssessStreamRequest(user_message="What is 2+2?")
    assert with_msg.user_message == "What is 2+2?"
