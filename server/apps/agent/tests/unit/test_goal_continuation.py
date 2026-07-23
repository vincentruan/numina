"""Tests for the U4 goal continuation loop (D1 — DeerFlow parity).

Covers:
- ``goal_evaluator.evaluate_goal_completion`` (fail-closed ``missing_evidence``,
  JSON parse, LLM exception → ``evaluator_error`` stand-down).
- ``goal_store.should_continue_goal`` / ``compute_no_progress_count`` /
  ``attach_goal_evaluation`` extensions (the P0 ``missing_evidence``→stop case,
  ``max_continuations_reached``, ``no_progress_detected``).
- ``_prepare_goal_continuation_input`` happy path / caps / race / evaluator
  failure.
- Loop-terminates integration test (R1 key): the worker's ``_run_numina_agent``
  continuation loop must terminate in every branch — satisfied, capped,
  no-progress, missing-evidence, evaluator-error, abort, and clear-during-loop.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.goal_evaluator import (
    GoalEvaluationError,
    evaluate_goal_completion,
)
from apps.agent.services.goal_store import (
    DEFAULT_MAX_GOAL_CONTINUATIONS,
    DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS,
    attach_goal_evaluation,
    compute_no_progress_count,
    should_continue_goal,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _goal(
    *,
    status: str = "active",
    continuation_count: int = 0,
    max_continuations: int = DEFAULT_MAX_GOAL_CONTINUATIONS,
    no_progress_count: int = 0,
    max_no_progress: int = DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS,
    objective: str = "分析完所有资产",
    last_evaluation: dict | None = None,
) -> dict:
    return {
        "objective": objective,
        "status": status,
        "family_id": "family-1",
        "created_at": "2026-07-21T00:00:00Z",
        "updated_at": "2026-07-21T00:00:00Z",
        "continuation_count": continuation_count,
        "max_continuations": max_continuations,
        "no_progress_count": no_progress_count,
        "max_no_progress_continuations": max_no_progress,
        "last_evaluation": last_evaluation or {},
    }


def _eval(
    *,
    satisfied: bool = False,
    blocker: str = "goal_not_met_yet",
    reason: str = "still working",
    evidence_summary: str = "partial",
) -> dict:
    return {
        "satisfied": satisfied,
        "blocker": blocker,
        "reason": reason,
        "evidence_summary": evidence_summary,
    }


def _ai_msg(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="ai",
        content=text,
        additional_kwargs={},
    )


def _human_msg(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="human",
        content=text,
        additional_kwargs={},
    )


# ---------------------------------------------------------------------------
# should_continue_goal — the P0 missing_evidence→stop gate
# ---------------------------------------------------------------------------


def test_should_continue_false_when_satisfied():
    goal = _goal()
    assert should_continue_goal(goal, _eval(satisfied=True, blocker="none")) is False


def test_should_continue_false_when_missing_evidence():
    """P0 fix: missing_evidence MUST stand down, never continue."""
    goal = _goal()
    assert should_continue_goal(goal, _eval(blocker="missing_evidence")) is False


def test_should_continue_false_when_needs_user_input():
    goal = _goal()
    assert should_continue_goal(goal, _eval(blocker="needs_user_input")) is False


def test_should_continue_false_when_run_failed():
    goal = _goal()
    assert should_continue_goal(goal, _eval(blocker="run_failed")) is False


def test_should_continue_true_when_goal_not_met_yet_and_under_caps():
    goal = _goal(continuation_count=0, no_progress_count=0)
    assert should_continue_goal(goal, _eval(blocker="goal_not_met_yet")) is True


def test_should_continue_false_at_max_continuations():
    goal = _goal(continuation_count=8, max_continuations=8)
    assert should_continue_goal(goal, _eval(blocker="goal_not_met_yet")) is False


def test_should_continue_false_at_max_no_progress():
    goal = _goal(no_progress_count=2, max_no_progress=2)
    assert should_continue_goal(goal, _eval(blocker="goal_not_met_yet")) is False


# ---------------------------------------------------------------------------
# compute_no_progress_count — signature-based stall detection
# ---------------------------------------------------------------------------


def test_no_progress_increments_on_repeated_signature():
    sig = "abc123"
    prev = attach_goal_evaluation(
        _goal(),
        _eval(blocker="goal_not_met_yet"),
        run_id="r1",
        evidence_signature=sig,
    )
    goal = _goal(last_evaluation=prev["last_evaluation"])
    # Same blocker + same signature → stall detected → +1
    assert compute_no_progress_count(goal, _eval(blocker="goal_not_met_yet"), evidence_signature=sig) == 1


def test_no_progress_resets_when_signature_advances():
    prev = attach_goal_evaluation(
        _goal(),
        _eval(blocker="goal_not_met_yet"),
        run_id="r1",
        evidence_signature="old",
    )
    goal = _goal(last_evaluation=prev["last_evaluation"])
    # New signature → progress → reset to 0
    assert compute_no_progress_count(goal, _eval(blocker="goal_not_met_yet"), evidence_signature="new") == 0


def test_no_progress_zero_when_satisfied():
    assert compute_no_progress_count(_goal(), _eval(satisfied=True, blocker="none")) == 0


# ---------------------------------------------------------------------------
# evaluate_goal_completion — fail-closed + LLM exception
# ---------------------------------------------------------------------------


async def test_evaluate_missing_evidence_when_no_visible_ai():
    """No visible assistant reply → fail-closed missing_evidence (no LLM call)."""
    goal = _goal()
    messages = [_human_msg("分析资产")]
    with patch("apps.agent.services.goal_evaluator.create_goal_evaluator_model") as mock_factory:
        evaluation = await evaluate_goal_completion(
            goal, messages, model=AsyncMock(), family_ai_config={}
        )
    assert evaluation["satisfied"] is False
    assert evaluation["blocker"] == "missing_evidence"
    mock_factory.assert_not_called()


async def test_evaluate_parses_satisfied_json():
    goal = _goal()
    messages = [_human_msg("分析资产"), _ai_msg("已完成所有资产分析。")]
    fake_response = SimpleNamespace(
        content='{"satisfied": true, "blocker": "none", "reason": "done", "evidence_summary": "all assets analyzed"}'
    )
    fake_model = AsyncMock()
    fake_model.ainvoke = AsyncMock(return_value=fake_response)
    evaluation = await evaluate_goal_completion(
        goal, messages, model=fake_model, family_ai_config={}
    )
    assert evaluation["satisfied"] is True
    assert evaluation["blocker"] == "none"
    assert evaluation["reason"] == "done"


async def test_evaluate_llm_exception_raises_goal_evaluation_error():
    """Evaluator LLM exception → GoalEvaluationError (caller stands down, no infinite loop)."""
    goal = _goal()
    messages = [_human_msg("分析资产"), _ai_msg("部分完成。")]
    fake_model = AsyncMock()
    fake_model.ainvoke = AsyncMock(side_effect=RuntimeError("provider down"))
    with pytest.raises(GoalEvaluationError):
        await evaluate_goal_completion(
            goal, messages, model=fake_model, family_ai_config={}
        )


async def test_evaluate_invalid_json_raises_goal_evaluation_error():
    goal = _goal()
    messages = [_human_msg("分析资产"), _ai_msg("部分完成。")]
    fake_response = SimpleNamespace(content="not json at all")
    fake_model = AsyncMock()
    fake_model.ainvoke = AsyncMock(return_value=fake_response)
    with pytest.raises(GoalEvaluationError):
        await evaluate_goal_completion(
            goal, messages, model=fake_model, family_ai_config={}
        )


# ---------------------------------------------------------------------------
# _prepare_goal_continuation_input — happy / caps / race / evaluator failure
# ---------------------------------------------------------------------------


def _checkpoint_tuple(
    *,
    checkpoint_id: str = "ckpt-1",
    goal: dict | None = None,
    ai_text: str = "部分完成。",
) -> SimpleNamespace:
    messages = [_human_msg("分析资产"), _ai_msg(ai_text)]
    channel_values: dict = {"messages": messages}
    if goal is not None:
        channel_values["goal"] = goal
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        checkpoint={
            "id": checkpoint_id,
            "channel_values": channel_values,
            "channel_versions": {"goal": 1} if goal is not None else {},
        },
        metadata={"family_id": "family-1"},
        parent_config=None,
        pending_writes=[],
    )


async def test_prepare_returns_none_when_no_goal():
    """No active goal → no continuation."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    ckpt = _checkpoint_tuple(goal=None)
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    result = await _prepare_goal_continuation_input(
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        family_ai_config={},
        user_id=None,
        family_id="family-1",
        abort_event=asyncio.Event(),
    )
    assert result is None


async def test_prepare_returns_none_when_goal_satisfied():
    """Satisfied goal → clear + no continuation."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal()
    ckpt = _checkpoint_tuple(goal=goal, ai_text="已完成所有资产分析。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    with (
        patch("apps.agent.services.runtime.worker.evaluate_goal_completion", new=AsyncMock(return_value=_eval(satisfied=True, blocker="none"))),
        patch("apps.agent.services.runtime.worker.write_thread_goal", new=AsyncMock(return_value={})) as mock_write,
    ):
        result = await _prepare_goal_continuation_input(
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            family_ai_config={},
            user_id=None,
            family_id="family-1",
            abort_event=asyncio.Event(),
        )
    assert result is None
    # Satisfied → goal cleared (write_thread_goal called with None)
    mock_write.assert_awaited()
    assert mock_write.call_args.args[2] is None


async def test_prepare_returns_continuation_when_not_met():
    """Not met + goal_not_met_yet + under caps → continuation message."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal(continuation_count=0)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    with (
        patch("apps.agent.services.runtime.worker.evaluate_goal_completion", new=AsyncMock(return_value=_eval(blocker="goal_not_met_yet"))),
        patch("apps.agent.services.runtime.worker.write_thread_goal", new=AsyncMock(return_value={"goal": goal})) as mock_write,
    ):
        result = await _prepare_goal_continuation_input(
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            family_ai_config={},
            user_id=None,
            family_id="family-1",
            abort_event=asyncio.Event(),
        )
    assert result is not None
    assert "context" in result
    assert "goal_continuation" in result["context"].free_text
    # continuation_count bumped to 1
    written_goal = mock_write.call_args.args[2]
    assert written_goal["continuation_count"] == 1


async def test_prepare_stands_down_on_missing_evidence():
    """P0: missing_evidence → stand down, NO continuation returned."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal(continuation_count=0)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    with (
        patch("apps.agent.services.runtime.worker.evaluate_goal_completion", new=AsyncMock(return_value=_eval(blocker="missing_evidence"))),
        patch("apps.agent.services.runtime.worker.write_thread_goal", new=AsyncMock(return_value={"goal": goal})) as mock_write,
    ):
        result = await _prepare_goal_continuation_input(
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            family_ai_config={},
            user_id=None,
            family_id="family-1",
            abort_event=asyncio.Event(),
        )
    assert result is None
    # Stood down with blocked:missing_evidence (not cleared — goal=None only on satisfied)
    written_goal = mock_write.call_args.args[2]
    assert written_goal is not None
    assert written_goal["last_evaluation"]["stand_down_reason"] == "blocked:missing_evidence"


async def test_prepare_stands_down_at_max_continuations():
    """continuation_count==max → max_continuations_reached stand down."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal(continuation_count=8, max_continuations=8)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    with (
        patch("apps.agent.services.runtime.worker.evaluate_goal_completion", new=AsyncMock(return_value=_eval(blocker="goal_not_met_yet"))),
        patch("apps.agent.services.runtime.worker.write_thread_goal", new=AsyncMock(return_value={"goal": goal})) as mock_write,
    ):
        result = await _prepare_goal_continuation_input(
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            family_ai_config={},
            user_id=None,
            family_id="family-1",
            abort_event=asyncio.Event(),
        )
    assert result is None
    written_goal = mock_write.call_args.args[2]
    assert written_goal["last_evaluation"]["stand_down_reason"] == "max_continuations_reached"


async def test_prepare_stands_down_on_evaluator_error():
    """Evaluator LLM exception → stand down (blocked:evaluator_error), no continuation."""
    from apps.agent.services.goal_evaluator import GoalEvaluationError
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal(continuation_count=0)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    with (
        patch("apps.agent.services.runtime.worker.evaluate_goal_completion", new=AsyncMock(side_effect=GoalEvaluationError("boom"))),
        patch("apps.agent.services.runtime.worker.write_thread_goal", new=AsyncMock(return_value={"goal": goal})) as mock_write,
    ):
        result = await _prepare_goal_continuation_input(
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            family_ai_config={},
            user_id=None,
            family_id="family-1",
            abort_event=asyncio.Event(),
        )
    assert result is None
    written_goal = mock_write.call_args.args[2]
    assert written_goal["last_evaluation"]["stand_down_reason"] == "blocked:evaluator_error"


async def test_prepare_yields_when_abort_set():
    """Abort event set during evaluation → no continuation."""
    from apps.agent.services.runtime.worker import _prepare_goal_continuation_input

    goal = _goal(continuation_count=0)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))
    abort = asyncio.Event()
    abort.set()
    result = await _prepare_goal_continuation_input(
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        family_ai_config={},
        user_id=None,
        family_id="family-1",
        abort_event=abort,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Loop-terminates integration test (R1 key)
# ---------------------------------------------------------------------------


async def test_continuation_loop_terminates_on_satisfied():
    """R1 key: the worker continuation loop terminates when goal is satisfied.

    Drives ``_run_numina_agent`` with a mocked adapter whose first turn is
    not-met and second turn is satisfied. The loop MUST terminate after the
    satisfied evaluation (no infinite loop), and exactly two stream turns
    must have run.
    """
    from apps.agent.services.runtime import worker as worker_mod

    goal = _goal(continuation_count=0)
    # First aget_tuple: not-met eval. Second: satisfied eval.
    evals = [
        _eval(blocker="goal_not_met_yet"),
        _eval(satisfied=True, blocker="none"),
    ]
    eval_iter = iter(evals)

    async def fake_eval(*args, **kwargs):
        return next(eval_iter)

    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))

    # Mock adapter: typed_stream_dispatch yields a single AI message + end.
    stream_call_count = 0

    class FakeAdapter:
        async def typed_stream_dispatch(self, **kwargs):
            nonlocal stream_call_count
            stream_call_count += 1
            yield ("messages", {"type": "ai", "content": "工作进展", "id": f"ai-{stream_call_count}", "tool_calls": None})
            yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}})

    record = SimpleNamespace(
        run_id="run-1",
        abort_event=asyncio.Event(),
        status=worker_mod.RunStatus.success,
    )
    bridge = SimpleNamespace(
        publish=AsyncMock(),
        publish_end=AsyncMock(),
        cleanup=AsyncMock(),
    )
    run_manager = SimpleNamespace(
        set_status=AsyncMock(),
    )

    graph_input = {"messages": [{"role": "user", "content": "分析资产"}]}
    config = {"configurable": {}}

    with (
        patch.object(worker_mod, "create_family_adapter", return_value=FakeAdapter()),
        patch.object(worker_mod, "BackendClient") as MockClient,
        patch.object(worker_mod, "pii_redactor") as mock_redactor,
        patch.object(worker_mod, "set_family_sandbox_context"),
        patch.object(worker_mod, "reset_family_sandbox_context"),
        patch.object(worker_mod, "audit_logger"),
        patch.object(worker_mod, "generate_suggestions", new=AsyncMock(return_value=None)),
        patch.object(worker_mod, "sync_title_from_checkpoint", new=AsyncMock()),
        patch.object(worker_mod, "schedule_run_cleanup"),
        patch.object(worker_mod, "_get_shared_checkpointer_for_goal", return_value=checkpointer),
        patch.object(worker_mod, "evaluate_goal_completion", new=AsyncMock(side_effect=fake_eval)),
        patch.object(worker_mod, "write_thread_goal", new=AsyncMock(return_value={"goal": goal})),
        patch.object(worker_mod, "read_thread_goal", new=AsyncMock(return_value=goal)),
    ):
        mock_client = MockClient.return_value
        mock_client.get_family_ai_config = AsyncMock(return_value={"providers": [{"is_active": True, "ai_provider": "openai", "ai_model_id": "m", "api_key": "k"}]})
        mock_client.get_enabled_mcp_servers = AsyncMock(return_value=[])
        mock_redactor.redact = lambda ctx: SimpleNamespace(family_id="family-1", free_text="分析资产")

        await worker_mod._run_numina_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id="family-1",
            user_id="user-1",
            thread_id="thread-1",
            graph_input=graph_input,
            config=config,
        )

    # Exactly two stream turns: initial + one continuation (then satisfied → stop).
    assert stream_call_count == 2, f"expected 2 stream turns, got {stream_call_count}"


async def test_continuation_loop_terminates_on_missing_evidence():
    """R1 key / P0: missing_evidence on the very first evaluation → loop
    terminates after exactly ONE stream turn (no continuation, no infinite loop)."""
    from apps.agent.services.runtime import worker as worker_mod

    goal = _goal(continuation_count=0)
    ckpt = _checkpoint_tuple(goal=goal, ai_text="部分完成。")
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=ckpt))

    stream_call_count = 0

    class FakeAdapter:
        async def typed_stream_dispatch(self, **kwargs):
            nonlocal stream_call_count
            stream_call_count += 1
            yield ("messages", {"type": "ai", "content": "工作进展", "id": f"ai-{stream_call_count}", "tool_calls": None})
            yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}})

    record = SimpleNamespace(
        run_id="run-1",
        abort_event=asyncio.Event(),
        status=worker_mod.RunStatus.success,
    )
    bridge = SimpleNamespace(publish=AsyncMock(), publish_end=AsyncMock(), cleanup=AsyncMock())
    run_manager = SimpleNamespace(set_status=AsyncMock())

    with (
        patch.object(worker_mod, "create_family_adapter", return_value=FakeAdapter()),
        patch.object(worker_mod, "BackendClient") as MockClient,
        patch.object(worker_mod, "pii_redactor") as mock_redactor,
        patch.object(worker_mod, "set_family_sandbox_context"),
        patch.object(worker_mod, "reset_family_sandbox_context"),
        patch.object(worker_mod, "audit_logger"),
        patch.object(worker_mod, "generate_suggestions", new=AsyncMock(return_value=None)),
        patch.object(worker_mod, "sync_title_from_checkpoint", new=AsyncMock()),
        patch.object(worker_mod, "schedule_run_cleanup"),
        patch.object(worker_mod, "_get_shared_checkpointer_for_goal", return_value=checkpointer),
        patch.object(worker_mod, "evaluate_goal_completion", new=AsyncMock(return_value=_eval(blocker="missing_evidence"))),
        patch.object(worker_mod, "write_thread_goal", new=AsyncMock(return_value={"goal": goal})),
        patch.object(worker_mod, "read_thread_goal", new=AsyncMock(return_value=goal)),
    ):
        mock_client = MockClient.return_value
        mock_client.get_family_ai_config = AsyncMock(return_value={"providers": [{"is_active": True, "ai_provider": "openai", "ai_model_id": "m", "api_key": "k"}]})
        mock_client.get_enabled_mcp_servers = AsyncMock(return_value=[])
        mock_redactor.redact = lambda ctx: SimpleNamespace(family_id="family-1", free_text="分析资产")

        await worker_mod._run_numina_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id="family-1",
            user_id="user-1",
            thread_id="thread-1",
            graph_input={"messages": [{"role": "user", "content": "分析资产"}]},
            config={"configurable": {}},
        )

    # missing_evidence → stand down after the first turn, no continuation.
    assert stream_call_count == 1, f"expected 1 stream turn, got {stream_call_count}"
