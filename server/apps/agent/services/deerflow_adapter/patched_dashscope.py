"""Patched ChatOpenAI for DashScope/Qwen thinking models.

DashScope (Alibaba Cloud) serves Qwen/QwQ models through an OpenAI-compatible
API that returns ``reasoning_content`` in streaming deltas when thinking mode
is enabled (``extra_body.enable_thinking: true``).  Standard
``langchain_openai.ChatOpenAI`` silently drops this vendor-specific field at
the model layer — downstream stream processing never sees it.

This module follows the upstream per-vendor patched class pattern
(``PatchedChatDeepSeek``, ``PatchedChatStepFun``, ``PatchedChatOpenAI``):

1. **Streaming capture** — override ``_convert_chunk_to_generation_chunk`` to
   extract ``reasoning_content`` from the raw delta dict and inject into
   ``AIMessageChunk.additional_kwargs["reasoning_content"]``.
2. **Non-streaming capture** — override ``_create_chat_result`` to extract
   reasoning from the response message dict.
3. **Multi-turn replay** — override ``_get_request_payload`` to restore
   ``reasoning_content`` on historical assistant messages using DeerFlow's
   ``restore_assistant_payloads``.

Downstream pipeline (unchanged):
- ``run_pipeline.py`` ``_dispatch_once`` with ``enable_reasoning_delta=True``
  publishes ``reasoning_delta`` custom events from
  ``additional_kwargs["reasoning_content"]``.

Removability: when ``langchain-openai`` handles ``reasoning_content`` natively
for all OpenAI-compatible APIs, delete this file and revert ``model_entry.py``
routing to stock ``ChatOpenAI``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from deerflow.models.assistant_payload_replay import (
    restore_assistant_payloads,
    restore_reasoning_content,
)
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

_MISSING = object()


# ---------------------------------------------------------------------------
# Reasoning extraction helpers
# ---------------------------------------------------------------------------


def _extract_reasoning(value: Any) -> str | object:
    """Extract ``reasoning_content`` from a streaming delta or message dict.

    DashScope/Qwen uses ``reasoning_content`` (same field as DeepSeek).
    Handles plain dicts, Pydantic/SDK objects, and ``model_extra`` fallback.
    """
    if isinstance(value, Mapping):
        rc = value.get("reasoning_content")
        if rc is not None:
            return rc
        return _MISSING

    attr = getattr(value, "reasoning_content", _MISSING)
    if attr is not _MISSING and attr is not None:
        return attr

    model_extra = getattr(value, "model_extra", None)
    if isinstance(model_extra, Mapping):
        rc = model_extra.get("reasoning_content")
        if rc is not None:
            return rc

    return _MISSING


def _with_reasoning_content(
    message: AIMessage | AIMessageChunk,
    reasoning: str,
) -> AIMessage | AIMessageChunk:
    """Return a copy of *message* with reasoning_content in additional_kwargs."""
    additional_kwargs = dict(message.additional_kwargs)
    if additional_kwargs.get("reasoning_content") != reasoning:
        additional_kwargs["reasoning_content"] = reasoning
    return message.model_copy(update={"additional_kwargs": additional_kwargs})


def _get_typed_choice_message(response: Any, index: int) -> Any:
    """Extract the SDK-typed choice message at *index*, if available."""
    choices = getattr(response, "choices", None)
    if choices is None:
        return None
    try:
        return choices[index].message
    except (AttributeError, IndexError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Patched model class
# ---------------------------------------------------------------------------


class PatchedChatDashScope(ChatOpenAI):
    """ChatOpenAI with reasoning_content capture for DashScope/Qwen APIs.

    DashScope serves Qwen/QwQ models via an OpenAI-compatible endpoint that
    returns ``reasoning_content`` in streaming deltas when thinking is enabled.
    This patched class captures that field into
    ``AIMessageChunk.additional_kwargs["reasoning_content"]`` — the same field
    the downstream pipeline (``run_pipeline._dispatch_once``) reads for
    ``reasoning_delta`` SSE events.

    Used for DashScope/Qwen/QwQ models with ``supports_thinking=True``.
    """

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"api_key": "OPENAI_API_KEY"}

    # --- Request payload replay (multi-turn) ---

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Restore reasoning_content on historical assistant messages.

        Uses DeerFlow's ``restore_assistant_payloads`` which handles length
        mismatches between payload and original messages via content +
        tool_call signature matching.
        """
        original_messages = self._convert_input(input_).to_messages()
        # Filter out error-fallback messages (matching upstream PatchedChatDeepSeek).
        # DeerFlow marks failed tool results with deerflow_error_fallback in
        # additional_kwargs; sending these to the vendor API would cause errors.
        filtered_messages = [
            m
            for m in original_messages
            if not (
                isinstance(m, AIMessage)
                and (m.additional_kwargs or {}).get("deerflow_error_fallback")
            )
        ]
        payload = super()._get_request_payload(filtered_messages, stop=stop, **kwargs)

        payload_messages = payload.get("messages", [])
        restore_assistant_payloads(
            payload_messages, original_messages, restore_reasoning_content
        )

        return payload

    # --- Streaming reasoning capture ---

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """Capture ``reasoning_content`` from DashScope streaming deltas."""
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None

        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta") or {}
            reasoning = _extract_reasoning(delta)
            if (
                reasoning is not _MISSING
                and isinstance(reasoning, str)
                and isinstance(generation_chunk.message, AIMessageChunk)
            ):
                generation_chunk = ChatGenerationChunk(
                    message=_with_reasoning_content(
                        generation_chunk.message, reasoning
                    ),
                    generation_info=generation_chunk.generation_info,
                )

        return generation_chunk

    # --- Non-streaming reasoning capture ---

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        """Extract ``reasoning_content`` from non-streaming responses."""
        result = super()._create_chat_result(response, generation_info)
        response_dict = (
            response if isinstance(response, dict) else response.model_dump()
        )
        choices = response_dict.get("choices", [])

        patched_generations: list[ChatGeneration] | None = None
        for index, generation in enumerate(result.generations):
            choice = choices[index] if index < len(choices) else {}
            choice_message = (
                choice.get("message", {}) if isinstance(choice, Mapping) else {}
            )
            reasoning = _extract_reasoning(choice_message)

            if reasoning is _MISSING and not isinstance(response, dict):
                reasoning = _extract_reasoning(
                    _get_typed_choice_message(response, index)
                )

            message = generation.message
            if (
                reasoning is not _MISSING
                and isinstance(reasoning, str)
                and isinstance(message, AIMessage)
            ):
                if patched_generations is None:
                    patched_generations = list(result.generations)
                patched_generations[index] = ChatGeneration(
                    message=_with_reasoning_content(message, reasoning),
                    generation_info=generation.generation_info,
                )

        return ChatResult(
            generations=patched_generations or result.generations,
            llm_output=result.llm_output,
        )
