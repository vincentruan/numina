"""Numina-side goal store: thin wrappers over DeerFlow's goal primitives.

DeerFlow's ``deerflow.runtime.goal`` provides the canonical
``read_thread_goal`` / ``write_thread_goal`` / ``build_goal_state`` /
``goal_thread_lock`` / ``GoalWriteConflict``. We re-export them here so the
router imports from a single numina-local module, and add a server-side
clamp (R1b) on ``max_continuations`` / ``max_no_progress_continuations`` as
defence-in-depth on top of Pydantic request validation.

KTD-5: ``from deerflow.runtime.goal import ...`` is verified to work in the
installed ``deerflow`` package (deerflow-harness workspace dependency), so we
inherit the correct ``aput(write_config, checkpoint, metadata, {"goal": next_version})``
4th-arg version-map semantics rather than hand-writing the read/write/clear.
"""

from __future__ import annotations

from typing import Any, cast

from deerflow.runtime.goal import (
    DEFAULT_MAX_GOAL_CONTINUATIONS,
    DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS,
    GoalWriteConflict,
    goal_thread_lock,
    read_thread_goal,
    write_thread_goal,
)
from deerflow.runtime.goal import (
    build_goal_state as _deerflow_build_goal_state,
)

__all__ = [
    "DEFAULT_MAX_GOAL_CONTINUATIONS",
    "DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS",
    "GoalWriteConflict",
    "build_goal_state",
    "goal_thread_lock",
    "read_thread_goal",
    "write_thread_goal",
]


def build_goal_state(
    objective: str,
    *,
    max_continuations: int = DEFAULT_MAX_GOAL_CONTINUATIONS,
    max_no_progress_continuations: int = DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS,
) -> dict:
    """Build a fresh active goal with server-side clamping (R1b).

    DeerFlow's ``build_goal_state`` already clamps ``max_continuations`` to
    ``DEFAULT_MAX_GOAL_CONTINUATIONS`` (8). We additionally clamp
    ``max_no_progress_continuations`` to ``[0, 2]`` here so a malicious or
    buggy client cannot request unbounded no-progress continuation turns.
    """
    clamped_no_progress = max(0, min(int(max_no_progress_continuations), DEFAULT_MAX_NO_PROGRESS_CONTINUATIONS))
    return cast(dict[str, Any], _deerflow_build_goal_state(
        objective,
        max_continuations=max_continuations,
        max_no_progress_continuations=clamped_no_progress,
    ))
