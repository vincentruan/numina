"""U4 goal evaluator: delegates to DeerFlow native ``evaluate_goal_completion``.

The evaluator runs from the worker after the user-visible turn has already
completed. It reuses Numina's own ``_create_lightweight_llm`` (family-active
provider, ``enable_thinking=False``) to create the model, then passes it to
DeerFlow's native ``evaluate_goal_completion(model=model, ...)`` which handles
the prompt, parsing, and fail-closed logic identically to our former custom
implementation (system prompt was character-for-character identical).

Why we pass ``model`` explicitly instead of using DeerFlow's
``create_goal_evaluator_model``: Numina does not carry a DeerFlow ``AppConfig``
on the worker path — the family AI config dict is what we have. Creating the
model via ``_create_lightweight_llm`` avoids the need for a global AppConfig
(which is process-wide and would race under multi-family concurrency).

Fail-closed: no visible assistant evidence → ``missing_evidence`` (handled by
native). LLM exception / invalid JSON → ``GoalEvaluationError`` so the worker
stands down (``blocked:evaluator_error``) rather than looping forever.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GoalEvaluationError(RuntimeError):
    """Raised when the goal evaluator LLM call or response parsing fails.

    The worker catches this and stands down with ``blocked:evaluator_error``
    so a failing evaluator can never drive an unbounded continuation loop.
    """


def create_goal_evaluator_model(
    family_ai_config: dict[str, Any], *, max_tokens: int = 300
) -> Any:
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

    Delegates to DeerFlow's native ``evaluate_goal_completion`` which handles
    fail-closed (no visible assistant evidence → ``missing_evidence``), prompt
    construction, and JSON parsing. The native returns a ``GoalEvaluation``
    TypedDict (dict-compatible) — our caller accesses it as a dict.

    Fail-closed: no visible assistant evidence → ``missing_evidence`` (no LLM
    call). LLM exception / invalid JSON → ``GoalEvaluationError`` (caller
    stands down with ``blocked:evaluator_error``).
    """
    from deerflow.runtime.goal import (
        evaluate_goal_completion as _native_evaluate,
    )

    if model is None:
        if family_ai_config is None:
            raise GoalEvaluationError(
                "evaluate_goal_completion requires a model or family_ai_config."
            )
        model = create_goal_evaluator_model(family_ai_config)

    try:
        evaluation = await _native_evaluate(
            goal,
            messages,
            model=model,
            thread_id=thread_id,
            user_id=user_id,
        )
    except ValueError as exc:
        # Native parse_goal_evaluation_response raises ValueError on bad JSON;
        # convert to our error type so the caller's catch clause still works.
        raise GoalEvaluationError(
            f"Goal evaluator response parsing failed: {exc}"
        ) from exc
    except Exception as exc:
        raise GoalEvaluationError(
            f"Goal evaluator LLM call failed: {exc}"
        ) from exc

    # Native returns GoalEvaluation (TypedDict = dict at runtime).
    return dict(evaluation)
