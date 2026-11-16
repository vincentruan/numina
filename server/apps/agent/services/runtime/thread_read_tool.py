"""Cross-thread message reader tool (T25 U6 — thread_read).

Provides the LLM with a way to read a specific past family conversation
by thread id. This is the read half of the ``thread_search`` /
``thread_read`` pair; together they satisfy R7-R8 without relying on the
upstream ``read_conversation`` host-gated tool, which does not wire
cleanly through Numina's embedded ``DeerFlowClient`` path.

The tool closes over ``family_id`` and a shared checkpointer at
construction. The checkpointer's ``aget_tuple`` is awaited inside the
tool's coroutine, which runs in DeerFlow's async tool-execution path.
All failures surface as ``{"error": "..."}`` JSON payloads rather than
raising, so the LLM always receives a structured response.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from apps.agent.services.conversation_reader import build_conversation_reader
from packages.core.logging import get_logger

logger = get_logger(__name__)


def _tool_error(message: str) -> str:
    return json.dumps({"error": message})


def _tool_payload(page_json: str) -> str:
    """Forward the reader's JSON payload, unchanged if it's valid JSON."""
    try:
        data = json.loads(page_json)
    except (json.JSONDecodeError, TypeError):
        return _tool_error(f"invalid_reader_output: {page_json!r}")
    if "error" in data:
        # Surface the error payload as-is — the model sees the same shape
        # whether the thread is missing, belongs to another family, or the
        # checkpointer failed.
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


async def _read(
    checkpointer: Any,
    family_id: str,
    thread_id: str,
    cursor: str | None,
    limit: int,
) -> str:
    """Invoke the bound conversation reader and return a JSON page."""
    if not thread_id or not isinstance(thread_id, str):
        return _tool_error("thread_id is required")

    if cursor is not None:
        try:
            int(cursor)
        except (ValueError, TypeError):
            return _tool_error("cursor must be a numeric string from a previous thread_read call")

    clamped_limit = max(1, min(int(limit or 20), 50))
    reader = build_conversation_reader(checkpointer, family_id)
    try:
        page = await reader(
            thread_id=thread_id,
            cursor=cursor,
            limit=clamped_limit,
        )
    except Exception:  # noqa: BLE001 — tool boundary
        logger.warning(
            "thread_read reader failed: thread_id=%s", thread_id, exc_info=True
        )
        return _tool_error("reader_failed")

    return _tool_payload(page)


def build_thread_read_tool(checkpointer: Any, family_id: str) -> StructuredTool:
    """Build a thread_read tool bound to a checkpointer and family.

    The returned tool's coroutine closes over ``checkpointer`` and
    ``family_id``, so the LLM need not (and cannot) pass them.
    """

    async def _coroutine(
        thread_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> str:
        return await _read(checkpointer, family_id, thread_id, cursor, limit)

    return StructuredTool.from_function(
        coroutine=_coroutine,
        name="thread_read",
        description=(
            "Read past messages from a specific family conversation by thread_id. "
            "Returns paginated HumanMessage/AIMessage content as JSON. "
            "Use after thread_search to dive into a session you identified. "
            "Pass the returned next_cursor to continue reading further pages."
        ),
    )
