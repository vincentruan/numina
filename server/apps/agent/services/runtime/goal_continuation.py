"""Goal continuation loop for the chat runner (D1 — DeerFlow worker.py parity).

Extracts the goal-evaluation + continuation-loop helpers from ``worker.py`` so
they live in a focused, testable module instead of bloating the dispatch file.

DeerFlow's versions are private to its ``runtime/runs/worker.py`` module and
reference DeerFlow-only objects (``StreamBridge.publish`` of serialized
``values``, DeerFlow ``AppConfig``). Numina drives the same logic against its
own ``StreamBridge`` and the family AI config dict.

R1 isolation: removing this module + the ``while`` block in
``_run_numina_agent`` leaves goal set/clear/status (U2) + GoalStatusBar (U5)
fully functional, just without auto-continuation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.agent.schemas.context import FamilyContext
from apps.agent.services.goal_evaluator import (
    GoalEvaluationError,
    evaluate_goal_completion,
)
from apps.agent.services.goal_store import (
    GoalWriteConflict,
    attach_goal_evaluation,
    compute_no_progress_count,
    goal_thread_lock,
    latest_visible_assistant_signature,
    make_goal_continuation_message,
    read_thread_goal,
    should_continue_goal,
    visible_conversation_signature,
    write_thread_goal,
)
from apps.agent.services.pii_redactor import pii_redactor

logger = logging.getLogger(__name__)


def _get_shared_checkpointer_for_goal() -> Any:
    """Return the shared LangGraph checkpointer used for goal channel reads/writes.

    Thin indirection so tests can patch
    ``goal_continuation._get_shared_checkpointer_for_goal`` without touching the
    family-adapter cache module.
    """
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        _get_shared_checkpointer,
    )

    return _get_shared_checkpointer(None)


def _goal_checkpoint_id(checkpoint_tuple: Any) -> str | None:
    config = getattr(checkpoint_tuple, "config", {}) or {}
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    checkpoint_id = (
        configurable.get("checkpoint_id") if isinstance(configurable, dict) else None
    )
    if isinstance(checkpoint_id, str):
        return checkpoint_id
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    if isinstance(checkpoint, dict):
        checkpoint_id_value = checkpoint.get("id")
        if isinstance(checkpoint_id_value, str):
            return checkpoint_id_value
    return None


def _read_checkpoint_messages(checkpoint_tuple: Any) -> list[Any]:
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = (
        checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}
    )
    messages = (
        channel_values.get("messages", []) if isinstance(channel_values, dict) else []
    )
    return messages if isinstance(messages, list) else []


def _read_checkpoint_goal(checkpoint_tuple: Any) -> dict[str, Any] | None:
    import copy

    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = (
        checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}
    )
    raw_goal = channel_values.get("goal") if isinstance(channel_values, dict) else None
    return copy.deepcopy(raw_goal) if isinstance(raw_goal, dict) else None


def _goal_instance_matches(
    left: dict[str, Any] | None, right: dict[str, Any] | None
) -> bool:
    if not left or not right:
        return False
    same_status = left.get("status") == right.get("status") == "active"
    same_objective = left.get("objective") == right.get("objective")
    same_created_at = left.get("created_at") == right.get("created_at")
    return bool(same_status and same_objective and same_created_at)


def _has_durable_goal_turn_receipt(checkpoint_tuple: Any, messages: list[Any]) -> bool:
    """Return true when a completed visible assistant turn is safely checkpointed."""
    if _goal_checkpoint_id(checkpoint_tuple) is None:
        return False
    if getattr(checkpoint_tuple, "pending_writes", None):
        return False
    from deerflow.runtime.goal import has_visible_assistant_evidence

    if not has_visible_assistant_evidence(messages):
        return False
    # Last visible message must be an AI reply (turn completed).
    last_type: str | None = None
    for message in messages:
        mt = _goal_message_type(message)
        if mt in {"human", "ai"} and _goal_message_text(message).strip():
            last_type = mt
    return last_type == "ai"


def _goal_message_type(message: Any) -> str | None:
    value = getattr(message, "type", None)
    if value is None and isinstance(message, dict):
        value = message.get("type") or message.get("role")
    if value == "assistant":
        return "ai"
    if value == "user":
        return "human"
    return str(value) if value else None


def _goal_message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, list):
        parts = [
            item["text"]
            if isinstance(item, dict) and isinstance(item.get("text"), str)
            else item
            for item in content
        ]
        content = "".join(str(p) for p in parts)
    if not isinstance(content, str):
        content = str(content) if content is not None else ""
    return content.strip()


def _stand_down_reason(
    goal: dict[str, Any], evaluation: dict[str, Any], no_progress_count: int
) -> str | None:
    """Mirror DeerFlow goal.py:774-785 stand-down reasons."""
    if evaluation["satisfied"]:
        return None
    if evaluation["blocker"] != "goal_not_met_yet":
        return f"blocked:{evaluation['blocker']}"
    if int(goal.get("continuation_count", 0)) >= int(goal.get("max_continuations", 8)):
        return "max_continuations_reached"
    if no_progress_count >= int(goal.get("max_no_progress_continuations", 2)):
        return "no_progress_detected"
    return None


async def _reread_goal_and_checkpoint(
    checkpointer: Any, thread_id: str
) -> tuple[dict[str, Any] | None, Any]:
    goal = await read_thread_goal(checkpointer, thread_id)
    checkpoint_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
    return goal, checkpoint_tuple


async def _reread_checkpoint_tuple(checkpointer: Any, thread_id: str) -> Any:
    aget_tuple = getattr(checkpointer, "aget_tuple", None) or getattr(
        checkpointer, "get_tuple", None
    )
    if aget_tuple is None:
        return None
    import inspect

    result = aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    if inspect.isawaitable(result):
        result = await result
    return result


async def _persist_goal_evaluation(
    *,
    checkpointer: Any,
    thread_id: str,
    run_id: str,
    goal: dict[str, Any],
    evaluation: dict[str, Any],
    no_progress_count: int,
    continuation_count: int | None = None,
    stand_down_reason: str | None = None,
    evidence_signature: str = "",
) -> dict[str, Any] | None:
    """Persist the evaluation against the still-current goal instance.

    Lock scope (P3): the ``goal_thread_lock`` is held only across the
    read-modify-write (read fresh checkpoint → attach evaluation → write), never
    across LLM calls — so a racing ``DELETE /goal`` cannot deadlock.
    """
    from typing import cast

    try:
        async with goal_thread_lock(thread_id):
            checkpoint_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
            if checkpoint_tuple is None:
                return None
            current_goal = _read_checkpoint_goal(checkpoint_tuple)
            if current_goal is None or not _goal_instance_matches(goal, current_goal):
                return None
            # Defensive: compute continuation_count from the fresh current_goal
            # inside the lock — a racing continuation may have already bumped it.
            effective_count = continuation_count
            if effective_count is not None:
                current_count = int(current_goal.get("continuation_count", 0))
                effective_count = max(effective_count, current_count + 1)
            expected_checkpoint_id = _goal_checkpoint_id(checkpoint_tuple)
            updated_goal = cast(
                dict[str, Any],
                attach_goal_evaluation(
                    current_goal,
                    evaluation,
                    run_id=run_id,
                    continuation_count=effective_count,
                    no_progress_count=no_progress_count,
                    stand_down_reason=stand_down_reason,
                    evidence_signature=evidence_signature,
                ),
            )
            await write_thread_goal(
                checkpointer,
                thread_id,
                updated_goal,
                as_node="goal_evaluator",
                expected_checkpoint_id=expected_checkpoint_id,
            )
        return updated_goal
    except GoalWriteConflict:
        return None
    except Exception:
        logger.warning(
            "Could not persist goal evaluation for thread %s", thread_id, exc_info=True
        )
        return None


async def _prepare_goal_continuation_input(
    *,
    checkpointer: Any,
    thread_id: str,
    run_id: str,
    family_ai_config: dict[str, Any],
    family_id: str,
    user_id: str | None,
    abort_event: asyncio.Event,
) -> dict[str, Any] | None:
    """Evaluate the active goal and return a hidden continuation input if needed.

    Aligned with DeerFlow ``runtime/runs/worker.py:858-1047``. Returns a dict
    with the continuation ``context`` (a ``RedactedContext`` whose ``free_text``
    carries the hidden goal-continuation message) plus the bumped
    ``continuation_count``, or ``None`` when the loop should stop (satisfied,
    blocked, capped, raced, aborted, or evaluator error).

    P0 fix: ``missing_evidence`` and any non-``goal_not_met_yet`` blocker stand
    down (``should_continue_goal`` returns False) — DeerFlow stops on these, it
    does NOT continue on them.

    Lock scope (P3): the lock is held only across the read-modify-write
    segment (``goal_thread_lock``), never across the evaluator LLM call — so a
    racing ``DELETE /goal`` (which acquires the same lock) cannot deadlock
    against a long continuation evaluation.
    """
    if checkpointer is None:
        return None
    if abort_event.is_set():
        return None

    try:
        goal = await read_thread_goal(checkpointer, thread_id)
    except Exception:
        logger.warning(
            "Could not read goal for thread %s after run %s",
            thread_id,
            run_id,
            exc_info=True,
        )
        return None
    if not goal or goal.get("status") != "active":
        return None

    # Read the checkpoint for messages + a pre-evaluation signature.
    try:
        checkpoint_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
    except Exception:
        logger.warning(
            "Could not read checkpoint for goal eval thread %s",
            thread_id,
            exc_info=True,
        )
        return None
    if checkpoint_tuple is None:
        return None

    checkpoint_id_before = _goal_checkpoint_id(checkpoint_tuple)
    messages = _read_checkpoint_messages(checkpoint_tuple)
    conversation_signature_before = visible_conversation_signature(messages)
    evidence_signature = latest_visible_assistant_signature(messages)

    if not _has_durable_goal_turn_receipt(checkpoint_tuple, messages):
        evaluation = {
            "satisfied": False,
            "blocker": "run_failed",
            "reason": "No durable assistant end-of-turn receipt was available.",
            "evidence_summary": "",
        }
        no_progress_count = compute_no_progress_count(
            goal, evaluation, evidence_signature=evidence_signature
        )
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="no_durable_end_of_turn",
            evidence_signature=evidence_signature,
        )
        return None

    if abort_event.is_set():
        return None

    # Evaluate via the non-thinking LLM. On failure stand down (no infinite loop).
    try:
        evaluation = await evaluate_goal_completion(
            goal,
            messages,
            family_ai_config=family_ai_config,
            thread_id=thread_id,
            user_id=user_id,
        )
    except GoalEvaluationError as exc:
        logger.warning(
            "Goal evaluator failed for thread %s after run %s: %s",
            thread_id,
            run_id,
            exc,
        )
        evaluation = {
            "satisfied": False,
            "blocker": "evaluator_error",
            "reason": str(exc),
            "evidence_summary": "",
        }
        no_progress_count = compute_no_progress_count(
            goal, evaluation, evidence_signature=evidence_signature
        )
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="blocked:evaluator_error",
            evidence_signature=evidence_signature,
        )
        return None

    if abort_event.is_set():
        return None

    no_progress_count = compute_no_progress_count(
        goal, evaluation, evidence_signature=evidence_signature
    )

    # Re-check that neither the goal nor the visible conversation changed while
    # the evaluator ran — a user message or /goal clear racing the evaluation wins.
    try:
        current_goal, current_checkpoint_tuple = await _reread_goal_and_checkpoint(
            checkpointer, thread_id
        )
    except Exception:
        logger.warning(
            "Could not re-check goal state for thread %s after evaluation",
            thread_id,
            exc_info=True,
        )
        return None
    if (
        not _goal_instance_matches(goal, current_goal)
        or current_checkpoint_tuple is None
    ):
        return None
    checkpoint_changed = (
        _goal_checkpoint_id(current_checkpoint_tuple) != checkpoint_id_before
    )
    messages_changed = (
        visible_conversation_signature(
            _read_checkpoint_messages(current_checkpoint_tuple)
        )
        != conversation_signature_before
    )
    if checkpoint_changed or messages_changed:
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="thread_changed_after_evaluation",
            evidence_signature=evidence_signature,
        )
        return None

    # Satisfied → clear the goal (inside the lock, with conflict detection).
    if evaluation["satisfied"]:
        try:
            async with goal_thread_lock(thread_id):
                latest_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
                if latest_tuple is None:
                    return None
                latest_goal = _read_checkpoint_goal(latest_tuple)
                if latest_goal is None or not _goal_instance_matches(goal, latest_goal):
                    return None
                await write_thread_goal(
                    checkpointer,
                    thread_id,
                    None,
                    as_node="goal_evaluator",
                    expected_checkpoint_id=_goal_checkpoint_id(latest_tuple),
                )
        except GoalWriteConflict:
            return None
        except Exception:
            logger.warning(
                "Could not clear satisfied goal for thread %s", thread_id, exc_info=True
            )
        return None

    stand_down_reason = _stand_down_reason(goal, evaluation, no_progress_count)
    if stand_down_reason is not None or not should_continue_goal(
        goal, evaluation, no_progress_count=no_progress_count
    ):
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason=stand_down_reason,
            evidence_signature=evidence_signature,
        )
        return None

    # Bump continuation_count (inside the lock, defensive max against a racing bump).
    next_count = int(goal.get("continuation_count", 0)) + 1
    updated_goal = await _persist_goal_evaluation(
        checkpointer=checkpointer,
        thread_id=thread_id,
        run_id=run_id,
        goal=goal,
        evaluation=evaluation,
        no_progress_count=no_progress_count,
        continuation_count=next_count,
        evidence_signature=evidence_signature,
    )
    if updated_goal is None:
        return None

    # Final guard: verify the visible conversation did not change before queuing.
    try:
        latest_goal, latest_checkpoint_tuple = await _reread_goal_and_checkpoint(
            checkpointer, thread_id
        )
    except Exception:
        logger.warning(
            "Could not verify queued goal continuation for thread %s",
            thread_id,
            exc_info=True,
        )
        return None
    if (
        not _goal_instance_matches(updated_goal, latest_goal)
        or latest_checkpoint_tuple is None
    ):
        return None
    if (
        visible_conversation_signature(
            _read_checkpoint_messages(latest_checkpoint_tuple)
        )
        != conversation_signature_before
    ):
        assert latest_goal is not None  # _goal_instance_matches guarantees non-None
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=latest_goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="thread_changed_before_continuation",
            evidence_signature=evidence_signature,
        )
        return None

    logger.info(
        "Run %s continuing thread %s for active goal (%d/%d)",
        run_id,
        thread_id,
        updated_goal.get("continuation_count", next_count),
        updated_goal.get("max_continuations", 0),
    )
    # Build the hidden continuation message and wrap it in a RedactedContext so
    # the adapter streams it as the next turn's user input. The frontend hides
    # human messages during active streaming (useThreadChat `!isInitialLoad`
    # filter), so this continuation is not shown as a duplicate user bubble.
    continuation_message = make_goal_continuation_message(updated_goal, evaluation)
    continuation_context = pii_redactor.redact(
        FamilyContext(family_id=family_id, free_text=continuation_message.content)
    )
    return {
        "context": continuation_context,
        "continuation_count": updated_goal.get("continuation_count", next_count),
    }
