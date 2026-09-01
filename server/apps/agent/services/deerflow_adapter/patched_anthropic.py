"""Patched ChatAnthropic that captures reasoning from Anthropic streaming events.

DeerFlow's ``_extract_text()`` silently drops thinking blocks from the content
list — it only extracts ``block.get("text")``, ignoring ``{"type": "thinking",
"thinking": "..."}`` blocks.  This means the pipeline's reasoning_delta handler
(which checks ``content`` list for thinking blocks) is dead code: by the time
events reach the pipeline, DeerFlow has already stripped thinking content.

This patch intercepts thinking at the **model layer** (before DeerFlow's client
processes the events) and copies thinking text into
``additional_kwargs["reasoning_content"]`` — the same field used by
``PatchedChatReasoning`` for OpenAI-compatible APIs.  The pipeline's
``additional_kwargs.get("reasoning_content")`` path (which IS reachable) then
captures it correctly.

Removability: when DeerFlow's ``_extract_text`` preserves thinking blocks in
the content list (or yields them through ``additional_kwargs``), delete this
file and revert ``model_entry.py`` routing to stock ``ChatAnthropic``.
"""

from __future__ import annotations

import logging

from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


class PatchedChatAnthropic(ChatAnthropic):
    """ChatAnthropic with reasoning capture for Anthropic extended thinking.

    Overrides ``_make_message_chunk_from_anthropic_event`` to extract thinking
    text from streaming deltas and inject into
    ``AIMessageChunk.additional_kwargs["reasoning_content"]``.  This bypasses
    DeerFlow's ``_extract_text`` which silently drops thinking blocks.

    Used for any Anthropic model with ``supports_thinking=True``.
    """

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"anthropic_api_key": "ANTHROPIC_API_KEY"}

    def _make_message_chunk_from_anthropic_event(self, event, *, stream_usage=True, coerce_content_to_string=False, block_start_event=None):
        """Capture thinking from Anthropic streaming events.

        Calls the parent method to get the original message chunk, then
        extracts thinking text from content blocks and copies to
        ``additional_kwargs["reasoning_content"]``.
        """
        message_chunk, new_block_start = super()._make_message_chunk_from_anthropic_event(
            event,
            stream_usage=stream_usage,
            coerce_content_to_string=coerce_content_to_string,
            block_start_event=block_start_event,
        )

        if message_chunk is None:
            return message_chunk, new_block_start

        # Extract thinking text from content blocks
        content = message_chunk.content
        if isinstance(content, list):
            thinking_parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    thinking_text = block.get("thinking")
                    if isinstance(thinking_text, str) and thinking_text:
                        thinking_parts.append(thinking_text)

            if thinking_parts:
                reasoning = "".join(thinking_parts)
                additional_kwargs = dict(message_chunk.additional_kwargs)
                # Append to existing reasoning_content (streaming accumulates)
                existing = additional_kwargs.get("reasoning_content", "")
                additional_kwargs["reasoning_content"] = existing + reasoning
                message_chunk = message_chunk.model_copy(
                    update={"additional_kwargs": additional_kwargs}
                )

        return message_chunk, new_block_start
