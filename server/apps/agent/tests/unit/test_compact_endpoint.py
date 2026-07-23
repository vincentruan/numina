"""Tests for apps.agent.routers.threads — compact endpoint (U6).

``POST /{thread_id}/compact`` delegates to DeerFlow's canonical
``compact_thread_context`` (KTD-5). Covers happy path, edge (empty/new thread →
not_enough_messages; run in-flight → 409), error (LLM summarize failure → 503;
cross-family → 404 via checkpoint ownership), integration (result dict maps
correctly; aput sticks is verified via the canonical call), and security
(child role → 403, KTD-8).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from deerflow.runtime.context_compaction import ThreadCompactionResult
from fastapi import HTTPException

from apps.agent.routers.threads import (
    ThreadCompactRequest,
    compact_thread_endpoint,
)
from apps.agent.services.compact_service import (
    ContextCompactionDisabled,
    ContextCompactionFailed,
)


def _verified(role: str = "owner") -> SimpleNamespace:
    """Stand-in for VerifiedFamily."""
    return SimpleNamespace(family_id="family-1", user_id="user-1", role=role)


def _request() -> SimpleNamespace:
    """Stand-in for fastapi.Request carrying app.state.run_manager."""
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_manager=None)))


def _make_checkpoint_tuple(
    checkpoint_id: str = "ckpt-1",
    *,
    family_id: str = "family-1",
    messages: list | None = None,
) -> SimpleNamespace:
    channel_values: dict = {}
    if messages is not None:
        channel_values["messages"] = messages
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        checkpoint={
            "id": checkpoint_id,
            "channel_values": channel_values,
            "channel_versions": {},
        },
        metadata={"family_id": family_id, "created_at": "2026-07-21T00:00:00Z"},
        parent_config=None,
        pending_writes=[],
    )


def _mock_run_manager(inflight: bool = False) -> SimpleNamespace:
    rm = SimpleNamespace()
    rm.has_inflight = AsyncMock(return_value=inflight)
    return rm


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_compact_happy_path_returns_summary_and_counts():
    """Thread with history → 200 + {compacted, removed_count, preserved_count, summary_updated}."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}, {"id": "m2"}])
    compact_result = ThreadCompactionResult(
        thread_id="thread-1",
        compacted=True,
        removed_message_count=5,
        preserved_message_count=2,
        summary_updated=True,
        checkpoint_id="ckpt-new",
        total_tokens=120,
    )
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=AsyncMock(return_value=compact_result)) as mock_compact,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        result = await compact_thread_endpoint(
            "thread-1",
            ThreadCompactRequest(),
            _request(),
            "family-1",
            verified=_verified(),
        )

    assert result.compacted is True
    assert result.removed_count == 5
    assert result.preserved_count == 2
    assert result.summary_updated is True
    assert result.checkpoint_id == "ckpt-new"
    assert result.total_tokens == 120
    mock_compact.assert_awaited_once()
    # user_id + agent_name are forwarded; force=True is hardcoded in the
    # compact_service wrapper (verified in test_compact_service_force_default).
    assert mock_compact.call_args.kwargs.get("user_id") == "user-1"


async def test_compact_service_force_default_is_true():
    """The compact_service wrapper hardcodes force=True (manual invocation contract, KTD-5)."""
    from apps.agent.services import compact_service as svc

    captured: dict = {}

    async def fake_compact(checkpointer, thread_id, **kwargs):
        captured.update(kwargs)
        return ThreadCompactionResult(thread_id=thread_id, compacted=True)

    with patch.object(svc, "compact_thread_context", new=fake_compact):
        await svc.compact_thread("ckpt", "thread-1", user_id="u1")

    assert captured.get("force") is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

async def test_compact_empty_thread_returns_not_enough_messages():
    """Empty/new thread → not compacted, reason=not_enough_messages (200, not error)."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[])
    compact_result = ThreadCompactionResult(
        thread_id="thread-1",
        compacted=False,
        reason="not_enough_messages",
    )
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=AsyncMock(return_value=compact_result)),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        result = await compact_thread_endpoint(
            "thread-1",
            ThreadCompactRequest(),
            _request(),
            "family-1",
            verified=_verified(),
        )

    assert result.compacted is False
    assert result.reason == "not_enough_messages"


async def test_compact_run_in_flight_returns_409():
    """Run in-flight → 409 before compaction is attempted."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}])
    run_manager = _mock_run_manager(inflight=True)
    mock_compact = AsyncMock()
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=mock_compact),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 409
    mock_compact.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

async def test_compact_llm_failure_returns_503():
    """LLM summarize failure (ContextCompactionFailed) → 503."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}])
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch(
            "apps.agent.routers.threads.compact_thread",
            new=AsyncMock(side_effect=ContextCompactionFailed("boom")),
        ),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 503


async def test_compaction_disabled_returns_409():
    """Summarization disabled in config (ContextCompactionDisabled) → 409."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}])
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch(
            "apps.agent.routers.threads.compact_thread",
            new=AsyncMock(side_effect=ContextCompactionDisabled("off")),
        ),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 409


async def test_compact_cross_family_returns_404():
    """Cross-family thread → 404 via checkpoint family-ownership check (KTD-8)."""
    # Checkpoint exists but belongs to family-2; caller is family-1.
    checkpoint_tuple = _make_checkpoint_tuple(family_id="family-2", messages=[{"id": "m1"}])
    run_manager = _mock_run_manager(inflight=False)
    mock_compact = AsyncMock()
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=mock_compact),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 404
    mock_compact.assert_not_awaited()


async def test_compact_missing_thread_returns_404():
    """Thread checkpoint + session row both absent → 404 (LookupError never reached)."""
    run_manager = _mock_run_manager(inflight=False)
    mock_compact = AsyncMock()
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=mock_compact),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 404
    mock_compact.assert_not_awaited()


async def test_compact_lookup_error_from_canonical_returns_404():
    """canonical compact_thread_context raises LookupError when checkpoint missing post-ownership → 404."""
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}])
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch(
            "apps.agent.routers.threads.compact_thread",
            new=AsyncMock(side_effect=LookupError("not found")),
        ),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        with pytest.raises(HTTPException) as exc_info:
            await compact_thread_endpoint(
                "thread-1",
                ThreadCompactRequest(),
                _request(),
                "family-1",
                verified=_verified(),
            )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Security (KTD-8)
# ---------------------------------------------------------------------------

async def test_compact_child_role_returns_403():
    """Child role POST → 403 before any ownership/compaction work (KTD-8)."""
    mock_compact = AsyncMock()
    with (
        patch("apps.agent.routers.threads.AiSessionRepository"),
        patch("apps.agent.routers.threads.get_checkpointer"),
        patch("apps.agent.routers.threads.get_run_manager"),
        patch("apps.agent.routers.threads.compact_thread", new=mock_compact),
        pytest.raises(HTTPException) as exc_info,
    ):
        await compact_thread_endpoint(
            "thread-1",
            ThreadCompactRequest(),
            _request(),
            "family-1",
            verified=_verified(role="child"),
        )

    assert exc_info.value.status_code == 403
    mock_compact.assert_not_awaited()


async def test_compact_member_role_proceeds_past_gate():
    """Adult members (role='member') pass the role gate — matches backend require_adult.

    Regression guard: the gate previously used the never-issued literal 'adult'
    (frozenset {'owner','adult'}), 403'ing every role='member' adult. The backend
    ``require_adult`` admits {owner, member}; the agent gate must agree. See P1-B
    in the two-AI-apps review. This asserts the member role reaches the downstream
    compaction (does not raise 403).
    """
    checkpoint_tuple = _make_checkpoint_tuple(messages=[{"id": "m1"}, {"id": "m2"}])
    compact_result = ThreadCompactionResult(
        thread_id="thread-1", compacted=True, checkpoint_id="ckpt-new"
    )
    run_manager = _mock_run_manager(inflight=False)
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads.get_run_manager") as mock_get_rm,
        patch("apps.agent.routers.threads.compact_thread", new=AsyncMock(return_value=compact_result)) as mock_compact,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_rm.return_value = run_manager

        result = await compact_thread_endpoint(
            "thread-1",
            ThreadCompactRequest(),
            _request(),
            "family-1",
            verified=_verified(role="member"),
        )

    assert result.compacted is True
    mock_compact.assert_awaited_once()


# ---------------------------------------------------------------------------
# Integration: result dict mapping (R4 — canonical aput-sticks is inherited
# via direct import; this verifies the response translation contract).
# ---------------------------------------------------------------------------

async def test_result_to_dict_round_trips_all_fields():
    """result_to_dict maps every ThreadCompactionResult field to the response keys."""
    from apps.agent.services.compact_service import result_to_dict

    result = ThreadCompactionResult(
        thread_id="thread-1",
        compacted=True,
        reason=None,
        removed_message_count=8,
        preserved_message_count=3,
        summary_updated=True,
        checkpoint_id="ckpt-9",
        total_tokens=256,
    )
    d = result_to_dict(result)
    assert d == {
        "compacted": True,
        "reason": None,
        "removed_count": 8,
        "preserved_count": 3,
        "summary_updated": True,
        "checkpoint_id": "ckpt-9",
        "total_tokens": 256,
    }
    # ThreadCompactResponse accepts the mapped dict (integration contract).
    resp = ThreadCompactRequest  # sanity that the module imports
    del resp
    from apps.agent.routers.threads import ThreadCompactResponse

    ThreadCompactResponse(**d)


async def test_compact_service_delegates_to_canonical_compact_thread_context():
    """compact_service.compact_thread delegates to deerflow's compact_thread_context with force=True (KTD-5/R4)."""
    from apps.agent.services import compact_service as svc

    captured: dict = {}

    async def fake_canonical(checkpointer, thread_id, **kwargs):
        captured.update(kwargs)
        captured["checkpointer"] = checkpointer
        captured["thread_id"] = thread_id
        return ThreadCompactionResult(thread_id=thread_id, compacted=True)

    with patch.object(svc, "compact_thread_context", new=fake_canonical):
        result = await svc.compact_thread("ckpt", "thread-7", user_id="u1", agent_name="chat")

    assert captured["force"] is True
    assert captured["user_id"] == "u1"
    assert captured["agent_name"] == "chat"
    assert captured["thread_id"] == "thread-7"
    assert result.compacted is True

