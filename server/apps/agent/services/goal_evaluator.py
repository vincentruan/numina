"""U4 goal evaluator: a small non-thinking LLM that judges goal completion.

Aligned with DeerFlow ``runtime/goal.py:270-340``. The evaluator runs from the
worker after the user-visible turn has already completed, so — like
``oneshot_llm`` and ``MemoryUpdater`` — it makes a standalone model call outside
the main graph and therefore reuses Numina's own ``_create_lightweight_llm``
(family-active provider, ``enable_thinking=False``) instead of DeerFlow's
``create_goal_evaluator_model`` (which assumes a DeerFlow ``app_config``).

KTD-5 / OQ4: we reuse the family provider via ``_create_lightweight_llm`` rather
than DeerFlow's ``create_chat_model`` because Numina does not carry a DeerFlow
``AppConfig`` on the worker path — the family AI config dict is what we have.

Fail-closed: when there is no visible assistant evidence, the evaluator returns
``missing_evidence`` WITHOUT calling the LLM (matches DeerFlow goal.py:291-297).
On LLM exception or invalid JSON, we raise ``GoalEvaluationError`` so the
worker stands down (``blocked:evaluator_error``) rather than looping forever.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

MAX_GOAL_REASON_CHARS = 1000
MAX_GOAL_EVIDENCE_CHARS = 1000
MAX_GOAL_CONVERSATION_CHARS = 12000
MAX_GOAL_CONVERSATION_MESSAGES = 30

_GOAL_BLOCKERS: set[str] = {
    "none",
    "missing_evidence",
    "needs_user_input",
    "run_failed",
    "external_wait",
    "goal_not_met_yet",
}

_SYSTEM_INSTRUCTION = (
    "You are a strict completion evaluator for an AI coding assistant.\n"
    "Decide whether the active goal is fully satisfied using ONLY the visible conversation evidence.\n"
    "Do not assume files, commands, tests, or external state changed unless the conversation explicitly shows it.\n"
    "If the visible evidence is too weak to prove progress, fail closed with blocker missing_evidence.\n"
    "Use blocker needs_user_input when the assistant is waiting on the user, run_failed when the turn failed, "
    "external_wait when work is waiting on an outside system, goal_not_met_yet when useful autonomous work can continue, "
    "and none only when satisfied is true.\n"
    'Output exactly one JSON object: {"satisfied": boolean, "blocker": string, "reason": string, "evidence_summary": string}.'
)


class GoalEvaluationError(RuntimeError):
    """Raised when the goal evaluator LLM call or response parsing fails.

    The worker catches this and stands down with ``blocked:evaluator_error``
    so a failing evaluator can never drive an unbounded continuation loop.
    """


def _message_text(message: Any) -> str:
    """Extract trimmed text from a langchain message or dict."""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, list):
        # Tool-call AI messages may carry content as a list of parts.
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        content = "".join(parts)
    if not isinstance(content, str):
        content = str(content) if content is not None else ""
    return content.strip()


def _message_type(message: Any) -> str | None:
    value = getattr(message, "type", None)
    if value is None and isinstance(message, dict):
        value = message.get("type") or message.get("role")
    if value == "assistant":
        return "ai"
    if value == "user":
        return "human"
    return str(value) if value else None


def _additional_kwargs(message: Any) -> dict[str, Any]:
    value = getattr(message, "additional_kwargs", None)
    if value is None and isinstance(message, dict):
        value = message.get("additional_kwargs")
    return dict(value) if isinstance(value, dict) else {}


def _is_visible_message(message: Any) -> bool:
    if _additional_kwargs(message).get("hide_from_ui") is True:
        return False
    return _message_type(message) in {"human", "ai"}


def _has_visible_assistant_evidence(messages: list[Any]) -> bool:
    return any(
        _is_visible_message(message)
        and _message_type(message) == "ai"
        and bool(_message_text(message))
        for message in messages
    )


def _format_visible_conversation(messages: list[Any]) -> str:
    lines: list[str] = []
    visible = [message for message in messages if _is_visible_message(message)]
    for message in visible[-MAX_GOAL_CONVERSATION_MESSAGES:]:
        text = _message_text(message)
        if not text:
            continue
        role = "User" if _message_type(message) == "human" else "Assistant"
        lines.append(f"{role}: {text}")
    conversation = "\n\n".join(lines)
    if len(conversation) > MAX_GOAL_CONVERSATION_CHARS:
        conversation = conversation[-MAX_GOAL_CONVERSATION_CHARS:]
    return conversation


def _normalize_text(value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:max_chars]


def _normalize_blocker(value: object, *, satisfied: bool) -> str:
    if satisfied:
        return "none"
    if isinstance(value, str) and value in _GOAL_BLOCKERS and value != "none":
        return value
    return "missing_evidence"


def _strip_artifacts(text: str) -> str:
    """Best-effort strip of markdown fences and <think> blocks from LLM output."""
    # Strip <think>...</think>
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>", start)
        if end == -1:
            break
        text = text[:start] + text[end + len("</think>") :]
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_goal_evaluation_response(text: str) -> dict[str, Any]:
    """Parse the evaluator's JSON object response into a GoalEvaluation dict."""
    candidate = _strip_artifacts(text)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GoalEvaluationError("Goal evaluator response did not contain a JSON object.")
    try:
        payload = json.loads(candidate[start : end + 1])
    except Exception as exc:
        raise GoalEvaluationError("Goal evaluator response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise GoalEvaluationError("Goal evaluator JSON must be an object.")
    satisfied = payload.get("satisfied")
    if not isinstance(satisfied, bool):
        raise GoalEvaluationError("Goal evaluator JSON must include boolean 'satisfied'.")
    reason = _normalize_text(payload.get("reason"), max_chars=MAX_GOAL_REASON_CHARS)
    evidence_summary = _normalize_text(payload.get("evidence_summary"), max_chars=MAX_GOAL_EVIDENCE_CHARS)
    blocker = _normalize_blocker(payload.get("blocker"), satisfied=satisfied)
    return {
        "satisfied": satisfied,
        "blocker": blocker,
        "reason": reason,
        "evidence_summary": evidence_summary,
    }


def create_goal_evaluator_model(family_ai_config: dict[str, Any], *, max_tokens: int = 300) -> Any:
    """Build the non-thinking chat model used by the goal evaluator.

    Reuses Numina's ``_create_lightweight_llm`` (family-active provider,
    ``enable_thinking=False``) — see module docstring for why we don't call
    DeerFlow's ``create_goal_evaluator_model``. Imported lazily to avoid a
    circular import (``runtime.__init__`` eagerly imports ``worker``, which
    imports this module).
    """
    from apps.agent.services.runtime.run_extras import _create_lightweight_llm

    return _create_lightweight_llm(
        family_ai_config,
        temperature=0.0,
        max_tokens=max_tokens,
    )


async def evaluate_goal_completion(
    goal: dict[str, Any],
    messages: list[Any],
    *,
    model: Any | None = None,
    family_ai_config: dict[str, Any] | None = None,
    thread_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Ask a small non-thinking model whether the active goal is satisfied.

    Fail-closed: no visible assistant evidence → ``missing_evidence`` (no LLM
    call). LLM exception / invalid JSON → ``GoalEvaluationError`` (caller
    stands down with ``blocked:evaluator_error``).
    """
    conversation = _format_visible_conversation(messages)
    if not conversation or not _has_visible_assistant_evidence(messages):
        return {
            "satisfied": False,
            "blocker": "missing_evidence",
            "reason": "No visible assistant evidence is available yet.",
            "evidence_summary": "",
        }

    if model is None:
        if family_ai_config is None:
            raise GoalEvaluationError("evaluate_goal_completion requires a model or family_ai_config.")
        model = create_goal_evaluator_model(family_ai_config)

    user_content = (
        f"Active goal:\n{goal.get('objective', '')}\n\n"
        f"Visible conversation evidence:\n{conversation}\n\n"
        "Is the active goal fully satisfied?"
    )
    try:
        response = await model.ainvoke(
            [SystemMessage(content=_SYSTEM_INSTRUCTION), HumanMessage(content=user_content)],
            config={"run_name": "goal_evaluator"},
        )
    except Exception as exc:
        raise GoalEvaluationError(f"Goal evaluator LLM call failed: {exc}") from exc

    text = response.content if isinstance(response.content, str) else str(response.content)
    return parse_goal_evaluation_response(text)
