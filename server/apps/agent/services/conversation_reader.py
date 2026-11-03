"""Conversation reader callback for DeerFlow's read_conversation tool (T25 U4).

The upstream ``read_conversation`` tool reads another thread's messages via a
host-provided reader callable bound to the current run. This module builds that
callable for Numina, validating family ownership against the LangGraph
checkpoint metadata and returning paginated, JSON-serialized messages.

The callable accepts the two shapes upstream uses:

* ``reader(thread_id, cursor=..., limit=...)`` — initial / next page.
* ``reader(thread_id, message_seq=..., offset=...)`` — continue a cut message.

The callable never raises into the tool loop; all failures are returned as
JSON ``{"error": "..."}`` payloads, which upstream surfaces verbatim to the
model.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from packages.core.logging import get_logger

logger = get_logger(__name__)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _message_to_dict(message: BaseMessage) -> dict[str, Any] | None:
    """Serialize a message to a JSON-friendly dict.

    Returns ``None`` for messages that should be filtered out (ToolMessage,
    SystemMessage, etc.). The upstream tool surfaces the JSON to the model,
    so only the content the model needs to see is included.
    """
    if not isinstance(message, (HumanMessage, AIMessage)):
        return None
    content = message.content
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)
    return {
        "type": "human" if isinstance(message, HumanMessage) else "ai",
        "content": content,
    }


def _paginate_messages(
    messages: list[BaseMessage],
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return a page of serialized messages plus the cursor for the next page.

    The cursor is the index of the first message in the next page (as a
    stringified integer), or ``None`` when no further page exists. The
    upstream tool forwards the cursor unchanged on the next call, so this
    reader owns the pagination scheme.
    """
    clamped_limit = max(1, min(limit, 50))

    start = int(cursor) if cursor else 0
    if start >= len(messages):
        return [], None

    page = messages[start : start + clamped_limit]
    serialized = [d for m in page if (d := _message_to_dict(m)) is not None]

    next_start = start + clamped_limit
    next_cursor: str | None = (
        str(next_start) if next_start < len(messages) else None
    )
    return serialized, next_cursor


def build_conversation_reader(
    checkpointer: Any,
    family_id: str,
) -> Callable[..., Any]:
    """Build the reader callable bound to a checkpointer and family scope.

    The returned callable validates that the requested ``thread_id`` belongs
    to ``family_id`` (via the checkpoint's ``family_id`` metadata) and returns
    a JSON page of serialized messages.

    The callable never raises; all failures are JSON ``{"error": "..."}``
    payloads.
    """

    async def _read(
        *,
        thread_id: str,
        cursor: str | None = None,
        limit: int = 20,
        message_seq: int | None = None,
        offset: int | None = None,
    ) -> str:
        try:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = await checkpointer.aget_tuple(config)
            if checkpoint_tuple is None:
                return _error(f"Thread {thread_id} not found")

            metadata = getattr(checkpoint_tuple, "metadata", {}) or {}
            ckpt_family_id = metadata.get("family_id")
            if not ckpt_family_id or str(ckpt_family_id) != str(family_id):
                return _error(f"Thread {thread_id} not found")

            checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
            channel_values = checkpoint.get("channel_values", {})
            raw_messages: list[BaseMessage] = list(
                channel_values.get("messages", []) or []
            )
            if not raw_messages:
                return json.dumps({"messages": [], "next_cursor": None})

            if message_seq is not None and offset is not None:
                # Continuation path — upstream expects a slice of one message's
                # text. For simplicity and because Numina stores whole messages
                # (not chunked), return the full message at message_seq-1.
                idx = message_seq - 1
                if idx < 0 or idx >= len(raw_messages):
                    return _error(
                        f"message_seq {message_seq} out of range (1..{len(raw_messages)})"
                    )
                msg = raw_messages[idx]
                content = msg.content if isinstance(msg.content, str) else json.dumps(
                    msg.content, ensure_ascii=False, default=str
                )
                return json.dumps(
                    {
                        "messages": [
                            {
                                "type": (
                                    "human" if isinstance(msg, HumanMessage) else "ai"
                                ),
                                "content": content[offset:],
                            }
                        ],
                        "message_seq": message_seq,
                        "offset": offset,
                        "remaining": max(0, len(content) - offset),
                    }
                )

            page, next_cursor = _paginate_messages(raw_messages, cursor, limit)
            return json.dumps({"messages": page, "next_cursor": next_cursor})

        except Exception:  # noqa: BLE001 — boundary to tool loop
            logger.exception(
                "conversation_reader failed: thread_id=%s family_id=%s",
                thread_id,
                family_id,
            )
            return _error(f"Failed to read thread {thread_id}")

    return _read
