"""Multi-tenant subagent background task registry.

Thin Numina wrapper around DeerFlow's global ``_background_tasks`` dict in
``deerflow.subagents.executor``, adding ``family_id`` scoping so each family
can only see and cancel its own background tasks.

DeerFlow's ``SubagentExecutor`` and its module-level ``_background_tasks``
dict are global singletons.  We cannot easily make them per-family without
forking the class, so this wrapper maintains a parallel index mapping
``task_id → family_id`` and provides per-tenant views.

# [Integrated with Numina Multi-Tenant] — family_id scoping over global registry
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from deerflow.subagents.executor import (
    get_background_task_result,
)

logger = logging.getLogger(__name__)

# Parallel index: task_id -> family_id
_family_task_index: dict[str, str] = {}
_family_index_lock = threading.Lock()


class FamilySubagentRegistry:
    """Per-family view over the global SubagentExecutor background task registry.

    Usage::

        registry = FamilySubagentRegistry()
        registry.register(family_id, task_id)
        tasks = registry.list_for_family(family_id)
        registry.request_cancel(family_id, task_id)
        registry.cleanup(family_id, task_id)
    """

    @staticmethod
    def register(family_id: str, task_id: str) -> None:
        """Associate *task_id* with *family_id* in the parallel index."""
        with _family_index_lock:
            _family_task_index[task_id] = family_id

    @staticmethod
    def list_for_family(family_id: str) -> list[Any]:
        """Return all non-None background task results for a family."""
        with _family_index_lock:
            task_ids = [
                tid for tid, fid in _family_task_index.items() if fid == family_id
            ]
        results: list[Any] = []
        for tid in task_ids:
            result = get_background_task_result(tid)
            if result is not None:
                results.append(result)
        return results

    @staticmethod
    def request_cancel(family_id: str, task_id: str) -> bool:
        """Request cancellation of a background task, verifying family ownership.

        Returns ``False`` when *task_id* is owned by a different family (cross-tenant
        cancel attempt rejected).  ``True`` when the cancel signal was sent (or the
        task is already in a terminal state).

        # [Integrated with Numina Multi-Tenant] — ownership check
        """
        with _family_index_lock:
            owner = _family_task_index.get(task_id)
        if owner != family_id:
            logger.warning(
                "[subagent] cross-tenant cancel rejected family=%s task=%s",
                family_id,
                task_id,
            )
            return False
        from deerflow.subagents.executor import request_cancel_background_task

        request_cancel_background_task(task_id)
        return True

    @staticmethod
    def cleanup(family_id: str, task_id: str) -> None:
        """Remove a completed task, verifying family ownership.

        Only removes tasks that are in a terminal state (avoids race with
        the background executor still updating the result).
        """
        with _family_index_lock:
            owner = _family_task_index.get(task_id)
        if owner != family_id:
            return
        from deerflow.subagents.executor import cleanup_background_task

        cleanup_background_task(task_id)
        with _family_index_lock:
            _family_task_index.pop(task_id, None)


def get_family_subagent_registry() -> FamilySubagentRegistry:
    """Return the singleton registry instance."""
    return FamilySubagentRegistry()
