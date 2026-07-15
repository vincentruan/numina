"""Tests for apps.agent.routers.threads — branch endpoint.

Regression guards for the /branches endpoint:
- ``branch_thread`` must create a new thread with copied checkpoint state
- Must validate family_id ownership
- Must find checkpoint containing target message_id
- Must return ThreadBranchResponse with correct metadata
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from apps.agent.routers.threads import (
    ThreadBranchRequest,
    branch_thread,
)


def _verified() -> SimpleNamespace:
    """Stand-in for VerifiedFamily."""
    return SimpleNamespace(family_id="family-1")


def _make_checkpoint_tuple(checkpoint_id: str, messages: list[dict]):
    """Helper to create a mock CheckpointTuple."""
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        checkpoint={
            "id": checkpoint_id,
            "channel_values": {"messages": messages},
            "channel_versions": {"messages": 1},
        },
        metadata={"family_id": "family-1", "created_at": "2026-07-13T00:00:00Z"},
        parent_config=None,
        pending_writes=[],
    )


def _mock_alist(items: list):
    """Create an async iterator mock for checkpointer.alist()."""

    async def alist_iter(*args, **kwargs):
        for item in items:
            yield item

    return alist_iter


async def test_branch_thread_success():
    """branch_thread must create a new thread with copied checkpoint state."""
    messages = [
        {"id": "msg-1", "role": "user", "content": "Hello"},
        {"id": "msg-2", "role": "assistant", "content": "Hi there"},
    ]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "title": "Original Thread",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(
            message_id="msg-2",
            message_ids=["msg-2"],
        )

        result = await branch_thread("thread-1", request, "family-1", verified=_verified())

        assert result.thread_id != "thread-1"
        assert result.parent_thread_id == "thread-1"
        assert result.parent_checkpoint_id == "ckpt-123"
        assert result.branched_from_message_id == "msg-2"

        # Verify session row was created
        repo.upsert.assert_awaited_once()
        call_args = repo.upsert.call_args
        assert call_args.kwargs["session_id"] == result.thread_id
        assert call_args.kwargs["family_id"] == "family-1"
        assert call_args.kwargs["source"] == "branch"

        # Verify title was set with "分支: " prefix
        repo.update_summary.assert_awaited_once()
        title_call = repo.update_summary.call_args
        assert title_call.kwargs["title"] == "分支: Original Thread"

        # Verify checkpoint was copied
        checkpointer.aput.assert_awaited_once()


async def test_branch_thread_404_when_session_not_found():
    """branch_thread must 404 when source session doesn't exist."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer"),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 404


async def test_branch_thread_404_when_family_id_mismatch():
    """branch_thread must 404 when family_id doesn't match."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer"),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-999",  # Different family
                "metadata": {},
            }
        )

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 404


async def test_branch_thread_409_when_message_not_found():
    """branch_thread must 409 when target message_id is not in any checkpoint."""
    messages = [
        {"id": "msg-1", "role": "user", "content": "Hello"},
    ]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])

        request = ThreadBranchRequest(
            message_id="msg-999",  # Not in checkpoint
            message_ids=["msg-999"],
        )

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 409
        assert "can no longer be branched from" in exc.value.detail


async def test_branch_thread_preserves_family_id_in_metadata():
    """branch_thread must copy family_id to new thread metadata."""
    messages = [{"id": "msg-1", "role": "assistant", "content": "Hi"}]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        await branch_thread("thread-1", request, "family-1", verified=_verified())

        # Verify aput was called with metadata containing family_id
        checkpointer.aput.assert_awaited_once()
        call_args = checkpointer.aput.call_args
        metadata = call_args[0][2]  # Third positional arg is metadata
        assert metadata["family_id"] == "family-1"
        assert metadata["numina_branch"] is True
        assert metadata["branch_parent_thread_id"] == "thread-1"
        assert metadata["branch_parent_checkpoint_id"] == "ckpt-123"
        assert metadata["branch_parent_message_id"] == "msg-1"
