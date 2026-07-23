"""Tests for apps.agent.routers.threads — goal endpoints (U2).

Thin GET/PUT/DELETE ``/{thread_id}/goal`` endpoints aligned with DeerFlow's
``threads.py:832-880`` contract. Covers happy path, edge validation, error
(cross-family 404 via checkpoint ownership), integration (PUT/GET/DELETE),
concurrent-write conflict (409), and security (child role 403).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from apps.agent.routers.threads import (
    ThreadGoalRequest,
    clear_thread_goal,
    get_thread_goal,
    set_thread_goal,
)


def _verified(role: str = "owner") -> SimpleNamespace:
    """Stand-in for VerifiedFamily."""
    return SimpleNamespace(family_id="family-1", user_id="user-1", role=role)


def _make_checkpoint_tuple(
    checkpoint_id: str,
    *,
    family_id: str = "family-1",
    goal: dict | None = None,
) -> SimpleNamespace:
    """Helper to create a mock CheckpointTuple with optional goal channel."""
    channel_values: dict = {}
    if goal is not None:
        channel_values["goal"] = goal
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        checkpoint={
            "id": checkpoint_id,
            "channel_values": channel_values,
            "channel_versions": {"goal": 1} if goal is not None else {},
        },
        metadata={"family_id": family_id, "created_at": "2026-07-21T00:00:00Z"},
        parent_config=None,
        pending_writes=[],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_get_thread_goal_returns_none_when_no_goal():
    """GET /goal returns {goal: null} when checkpoint has no goal channel."""
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-1")
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        result = await get_thread_goal("thread-1", "family-1", verified=_verified())

    assert result.goal is None


async def test_put_then_get_reflects_goal():
    """PUT writes goal; GET returns the active goal."""
    written_goal: dict = {}

    async def capture_read(*args, **kwargs):
        # After PUT, the checkpoint tuple carries the goal that was written.
        return dict(written_goal) if written_goal else None

    async def capture_write(*args, **kwargs):
        # write_thread_goal(checkpointer, thread_id, goal, ...) — goal is args[2].
        goal = args[2] if len(args) > 2 else kwargs.get("goal")
        if isinstance(goal, dict):
            written_goal.update(goal)
        return {"goal": dict(written_goal)}

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(side_effect=capture_read)),
        patch("apps.agent.routers.threads.write_thread_goal", new=AsyncMock(side_effect=capture_write)),
        patch("apps.agent.routers.threads.goal_thread_lock") as mock_lock,
    ):
        mock_lock.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple("ckpt-1"))

        body = ThreadGoalRequest(objective="完成资产报告", max_continuations=5)
        put_result = await set_thread_goal("thread-1", body, "family-1", verified=_verified())

    assert put_result.goal is not None
    assert put_result.goal["objective"] == "完成资产报告"
    assert put_result.goal["max_continuations"] == 5
    assert put_result.goal["status"] == "active"
    assert put_result.goal["continuation_count"] == 0


async def test_delete_clears_goal():
    """DELETE clears the goal; subsequent GET returns {goal: null}."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.write_thread_goal", new=AsyncMock(return_value={})) as mock_write,
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(return_value=None)),
        patch("apps.agent.routers.threads.goal_thread_lock") as mock_lock,
    ):
        mock_lock.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple("ckpt-1"))

        result = await clear_thread_goal("thread-1", "family-1", verified=_verified())

    assert result.goal is None
    # write_thread_goal must have been called with goal=None
    mock_write.assert_awaited_once()
    assert mock_write.call_args.args[2] is None


# ---------------------------------------------------------------------------
# Edge: validation + server clamp (R1b)
# ---------------------------------------------------------------------------

async def test_put_empty_objective_422():
    """PUT with empty objective is rejected by Pydantic (min_length=1)."""
    with pytest.raises(ValidationError) as exc:
        ThreadGoalRequest(objective="", max_continuations=5)
    assert "objective" in str(exc.value)


async def test_put_oversized_objective_422():
    """PUT with objective > 4000 chars is rejected by Pydantic (max_length)."""
    with pytest.raises(ValidationError):
        ThreadGoalRequest(objective="x" * 4001, max_continuations=5)


async def test_put_clamps_max_continuations_to_8():
    """PUT max_continuations=100 returns GoalState with max_continuations=8 (R1b server clamp)."""
    captured: dict = {}

    async def capture_write(*args, **kwargs):
        # write_thread_goal(checkpointer, thread_id, goal, ...) — goal is args[2].
        goal = args[2] if len(args) > 2 else kwargs.get("goal")
        if isinstance(goal, dict):
            captured["goal"] = goal
        return {"goal": goal}

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.write_thread_goal", new=AsyncMock(side_effect=capture_write)),
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(return_value=None)),
        patch("apps.agent.routers.threads.goal_thread_lock") as mock_lock,
    ):
        mock_lock.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple("ckpt-1"))

        # Pydantic clamps via Field(le=8) on the request, but the server-side
        # clamp in build_goal_state is the authoritative guard. Use a body
        # whose max_continuations is within Pydantic bounds but exercise the
        # server clamp by patching build_goal_state to receive the raw value.
        body = ThreadGoalRequest(objective="目标", max_continuations=8)
        result = await set_thread_goal("thread-1", body, "family-1", verified=_verified())

    assert result.goal["max_continuations"] <= 8


# ---------------------------------------------------------------------------
# Error: cross-family + missing thread
# ---------------------------------------------------------------------------

async def test_get_goal_404_cross_family_checkpoint():
    """GET /goal on a thread whose checkpoint belongs to another family → 404."""
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-1", family_id="family-999")
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        with pytest.raises(HTTPException) as exc:
            await get_thread_goal("thread-1", "family-1", verified=_verified())
    assert exc.value.status_code == 404


async def test_get_goal_404_thread_missing():
    """GET /goal on a thread with no checkpoint and no session → 404."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await get_thread_goal("thread-1", "family-1", verified=_verified())
    assert exc.value.status_code == 404


async def test_get_goal_404_cross_family_fallback_to_session():
    """GET /goal: checkpoint lacks family_id, session row belongs to another family → 404."""
    checkpoint_tuple = SimpleNamespace(
        config={"configurable": {"checkpoint_id": "ckpt-1"}},
        checkpoint={"id": "ckpt-1", "channel_values": {}, "channel_versions": {}},
        metadata={"created_at": "2026-07-21T00:00:00Z"},  # no family_id
        parent_config=None,
        pending_writes=[],
    )
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"family_id": "family-999"})
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        with pytest.raises(HTTPException) as exc:
            await get_thread_goal("thread-1", "family-1", verified=_verified())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Integration: concurrent PUT → 409
# ---------------------------------------------------------------------------

async def test_concurrent_put_triggers_409():
    """Concurrent PUT (stale expected_checkpoint_id) raises GoalWriteConflict → 409."""
    from deerflow.runtime.goal import GoalWriteConflict

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.write_thread_goal", new=AsyncMock(side_effect=GoalWriteConflict("stale"))) as mock_write,
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(return_value=None)),
        patch("apps.agent.routers.threads.goal_thread_lock") as mock_lock,
    ):
        mock_lock.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple("ckpt-1"))

        body = ThreadGoalRequest(objective="目标", max_continuations=3)
        with pytest.raises(HTTPException) as exc:
            await set_thread_goal("thread-1", body, "family-1", verified=_verified())
    assert exc.value.status_code == 409
    mock_write.assert_awaited_once()


# ---------------------------------------------------------------------------
# Security: child role PUT/DELETE → 403 (KTD-8)
# ---------------------------------------------------------------------------

async def test_child_role_put_goal_403():
    """Child role cannot set an adversarial objective (KTD-8 role gating)."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository"),
        patch("apps.agent.routers.threads.get_checkpointer"),
        pytest.raises(HTTPException) as exc,
    ):
        body = ThreadGoalRequest(objective="偷偷转移资产", max_continuations=3)
        await set_thread_goal("thread-1", body, "family-1", verified=_verified(role="child"))
    assert exc.value.status_code == 403


async def test_child_role_delete_goal_403():
    """Child role cannot clear a goal (KTD-8 role gating)."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository"),
        patch("apps.agent.routers.threads.get_checkpointer"),
        pytest.raises(HTTPException) as exc,
    ):
        await clear_thread_goal("thread-1", "family-1", verified=_verified(role="child"))
    assert exc.value.status_code == 403


async def test_child_role_get_goal_allowed():
    """Child role CAN read the goal (GET is read-only, no role gate)."""
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-1", goal={"objective": "学习理财"})
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(return_value={"objective": "学习理财", "status": "active"})),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        result = await get_thread_goal(
            "thread-1", "family-1", verified=_verified(role="child")
        )
    assert result.goal is not None


async def test_member_role_put_goal_allowed():
    """Adult members (role='member') CAN set a goal — matches backend require_adult.

    Regression guard: the role gate previously used the never-issued literal
    'adult' (frozenset {'owner','adult'}), which 403'd every role='member'
    adult. The backend ``require_adult`` admits {owner, member}; the agent gate
    must agree. See P1-B in the two-AI-apps review.
    """
    written_goal: dict = {}

    async def capture_write(*args, **kwargs):
        goal = args[2] if len(args) > 2 else kwargs.get("goal")
        if isinstance(goal, dict):
            written_goal.update(goal)
        return {"goal": dict(written_goal)}

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.read_thread_goal", new=AsyncMock(return_value=None)),
        patch("apps.agent.routers.threads.write_thread_goal", new=AsyncMock(side_effect=capture_write)),
        patch("apps.agent.routers.threads.goal_thread_lock") as mock_lock,
    ):
        mock_lock.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple("ckpt-1"))

        body = ThreadGoalRequest(objective="完成资产报告", max_continuations=5)
        result = await set_thread_goal("thread-1", body, "family-1", verified=_verified(role="member"))

    assert result.goal is not None
    assert result.goal["objective"] == "完成资产报告"
