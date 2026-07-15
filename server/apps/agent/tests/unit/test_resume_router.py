"""Unit tests for resume endpoint.

Verifies the resume endpoint validates thread ownership and returns
appropriate responses for valid/invalid requests.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


def _verified() -> SimpleNamespace:
    """Stand-in for VerifiedFamily — the endpoints never inspect it."""
    return SimpleNamespace(family_id="family-1", user_id="user-1", role="member")


async def test_resume_endpoint_validates_family_id():
    """resume_run must verify family_id ownership."""
    from apps.agent.routers.resume import resume_run, ResumeRequest
    from fastapi import HTTPException

    with patch("apps.agent.routers.resume.AiSessionRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)

        with patch("apps.agent.routers.resume._get_shared_checkpointer") as mock_ckpt:
            checkpointer = mock_ckpt.return_value
            checkpointer.aget_tuple = AsyncMock(return_value=None)

            request = ResumeRequest(answer="user answer", interrupt_id="interrupt-123")

            with pytest.raises(HTTPException) as exc_info:
                await resume_run(
                    thread_id="thread-1",
                    body=request,
                    request=None,
                    x_family_id="family-1",
                    x_user_id="user-1",
                    verified=_verified(),
                )

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail)


async def test_resume_endpoint_returns_success():
    """resume_run must return StreamingResponse after resuming graph."""
    from apps.agent.routers.resume import resume_run, ResumeRequest
    from fastapi.responses import StreamingResponse

    with patch("apps.agent.routers.resume.AiSessionRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={"family_id": "family-1", "thread_id": "thread-1"}
        )

        with patch("apps.agent.routers.resume.get_run_manager") as mock_run_mgr:
            run_mgr = mock_run_mgr.return_value
            run_record = SimpleNamespace(run_id="run-123", task=None)
            run_mgr.create_or_reject = AsyncMock(return_value=run_record)

            with patch("apps.agent.routers.resume.get_stream_bridge") as mock_bridge:
                bridge = mock_bridge.return_value

                with patch("apps.agent.routers.resume.run_family_agent") as mock_run:
                    mock_run.return_value = None

                    request = ResumeRequest(
                        answer="user answer", interrupt_id="interrupt-123"
                    )

                    # Mock Request object
                    mock_request = AsyncMock()
                    mock_request.is_disconnected = AsyncMock(return_value=False)

                    result = await resume_run(
                        thread_id="thread-1",
                        body=request,
                        request=mock_request,
                        x_family_id="family-1",
                        x_user_id="user-1",
                        verified=_verified(),
                    )

                    assert isinstance(result, StreamingResponse)
                    assert result.media_type == "text/event-stream"
                    assert "thread-1" in result.headers.get("Content-Location", "")
