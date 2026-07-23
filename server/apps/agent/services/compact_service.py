"""Numina-side compaction service: thin wrapper over DeerFlow's canonical compactor.

DeerFlow's ``deerflow.runtime.context_compaction.compact_thread_context`` is the
canonical implementation that correctly handles ``RemoveMessage(ALL)`` + preserved
tail + ``channel_versions`` bump + ``summary_text`` channel (KTD-5). We import and
delegate to it rather than hand-writing message partitioning — hand-writing is the
R4 root cause (LangGraph's default ``messages`` reducer re-accumulates by id, so a
naive short-list ``aput`` does not "stick" on the next run).

This module translates ``ThreadCompactionResult`` into the numina API response
shape and centralises the exception → HTTP status mapping so the router stays
thin. It deliberately does NOT reuse the agent-mounted ``SummarizationMiddleware``:
DeerFlow builds its own compaction middleware via ``_create_compaction_middleware``
(see context_compaction.py:40-48), so we inherit that behaviour by calling
``compact_thread_context`` directly.
"""

from __future__ import annotations

import logging
from typing import Any

from deerflow.runtime.context_compaction import (
    ContextCompactionDisabled,
    ContextCompactionFailed,
    ThreadCompactionResult,
    compact_thread_context,
)

logger = logging.getLogger(__name__)


async def compact_thread(
    checkpointer: Any,
    thread_id: str,
    *,
    user_id: str | None = None,
    agent_name: str | None = None,
) -> ThreadCompactionResult:
    """Summarize old thread context, preserving the visible tail.

    Thin wrapper around DeerFlow's ``compact_thread_context``. ``force=True``
    compacts regardless of token thresholds (manual user invocation), matching
    DeerFlow's ``POST /{thread_id}/compact`` default (threads.py:896-926).

    Raises:
        ContextCompactionDisabled: summarization disabled in app config → 409.
        ContextCompactionFailed: LLM summarize failure → 503.
        LookupError: thread checkpoint missing → 404.
    """
    return await compact_thread_context(
        checkpointer,
        thread_id,
        force=True,
        user_id=user_id,
        agent_name=agent_name,
    )


def result_to_dict(result: ThreadCompactionResult) -> dict[str, Any]:
    """Translate ``ThreadCompactionResult`` to the API response dict.

    Mirrors DeerFlow's ``_thread_compact_response`` (threads.py:883-893) but
    uses numina's response keys documented in the plan:
    ``compacted / removed_count / preserved_count / summary_updated`` plus the
    canonical ``reason`` / ``checkpoint_id`` / ``total_tokens`` fields.
    """
    return {
        "compacted": result.compacted,
        "reason": result.reason,
        "removed_count": result.removed_message_count,
        "preserved_count": result.preserved_message_count,
        "summary_updated": result.summary_updated,
        "checkpoint_id": result.checkpoint_id,
        "total_tokens": result.total_tokens,
    }


__all__ = [
    "ContextCompactionDisabled",
    "ContextCompactionFailed",
    "compact_thread",
    "result_to_dict",
]
