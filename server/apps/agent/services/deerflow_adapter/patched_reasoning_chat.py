"""Patched ChatOpenAI that captures reasoning fields from OpenAI-compatible APIs.

Several OpenAI-compatible vendors return non-standard reasoning fields in their
streaming deltas and response messages:

- ``reasoning_content`` (DashScope/Qwen, DeepSeek, StepFun)
- ``reasoning`` (StepFun default)
- ``thought_signature`` (Gemini via OpenAI gateway — required on tool-call objects
  in subsequent requests)

Standard ``langchain_openai.ChatOpenAI`` only extracts standard OpenAI fields
(``content``, ``tool_calls``, ``role``) from each delta — vendor-specific
reasoning fields are silently dropped at the **model layer**, before downstream
stream processing (DeerFlow ``client.py`` ``thinking_sink``, adapter
``_async_stream_chunks``, ``run_pipeline._dispatch_once``) even sees them.

This patch consolidates three concerns into one class so the routing decision
is based on API format (OpenAI-compatible + thinking), not on vendor identity:

1. **Streaming capture** — override ``_convert_chunk_to_generation_chunk`` to
   extract ``reasoning_content`` / ``reasoning`` from the raw delta dict and
   inject into ``AIMessageChunk.additional_kwargs["reasoning_content"]``.
2. **Non-streaming capture** — override ``_create_chat_result`` to extract
   reasoning from the response message dict.
3. **Multi-turn replay** — override ``_get_request_payload`` to restore both
   ``reasoning_content`` and ``thought_signature`` on historical assistant
   messages using DeerFlow's ``restore_assistant_payloads`` (which handles
   length mismatches via content+tool_call signature matching).

Downstream reasoning pipeline (already implemented, not modified by this patch):

- DeerFlow ``client.py`` ``_extract_text(content, thinking_sink=...)`` extracts
  thinking from content lists and merges into ``additional_kwargs.reasoning_content``.
- ``run_pipeline.py`` ``_dispatch_once`` with ``enable_reasoning_delta=True``
  publishes ``reasoning_delta`` custom events from ``additional_kwargs.reasoning_content``.

Removability: when ``langchain-openai`` handles reasoning fields natively,
delete this file and revert ``model_entry.py`` routing to stock ``ChatOpenAI``.
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
    """Extract reasoning content from a streaming delta or message dict.

    Checks ``reasoning_content`` first (DashScope, DeepSeek), then ``reasoning``
    (StepFun default).  Handles plain dicts, Pydantic/SDK objects, and
    ``model_extra`` fallback.
    """
    if isinstance(value, Mapping):
        for field in ("reasoning_content", "reasoning"):
            if field in value and value[field] is not None:
                return value[field]
        return _MISSING

    for field in ("reasoning_content", "reasoning"):
        attr = getattr(value, field, _MISSING)
        if attr is not _MISSING and attr is not None:
            return attr

    model_extra = getattr(value, "model_extra", None)
    if isinstance(model_extra, Mapping):
        for field in ("reasoning_content", "reasoning"):
            if field in model_extra and model_extra[field] is not None:
                return model_extra[field]

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


def _restore_tool_call_signatures(payload_msg: dict, orig_msg: AIMessage) -> None:
    """Re-inject ``thought_signature`` onto tool-call objects in *payload_msg*.

    Gemini via OpenAI gateway requires ``thought_signature`` on tool-call objects
    in subsequent requests.  langchain-openai serialises only standard fields
    (``id``, ``type``, ``function``), silently dropping the signature.
    """
    raw_tool_calls: list[dict] = orig_msg.additional_kwargs.get("tool_calls") or []
    payload_tool_calls: list[dict] = payload_msg.get("tool_calls") or []

    if not raw_tool_calls or not payload_tool_calls:
        return

    raw_by_id: dict[str, dict] = {}
    for raw_tc in raw_tool_calls:
        tc_id = raw_tc.get("id")
        if tc_id:
            raw_by_id[tc_id] = raw_tc

    for idx, payload_tc in enumerate(payload_tool_calls):
        raw_tc = raw_by_id.get(payload_tc.get("id", ""))
        if raw_tc is None and idx < len(raw_tool_calls):
            raw_tc = raw_tool_calls[idx]
        if raw_tc is None:
            continue

        sig = raw_tc.get("thought_signature") or raw_tc.get("thoughtSignature")
        if sig:
            payload_tc["thought_signature"] = sig


# ---------------------------------------------------------------------------
# Patched model class
# ---------------------------------------------------------------------------


class PatchedChatReasoning(ChatOpenAI):
    """ChatOpenAI with reasoning field capture for any LLM API that returns
    non-standard reasoning fields in streaming deltas or response messages.

    Captures vendor-specific reasoning fields (``reasoning_content``, ``reasoning``)
    from streaming deltas and non-streaming responses into
    ``AIMessage.additional_kwargs["reasoning_content"]``.  Also replays
    ``thought_signature`` (Gemini) on historical assistant messages for
    multi-turn tool-call conversations.

    Used for any LLM API with ``supports_thinking=True`` except DeepSeek
    (which uses its own patched class from ``langchain_deepseek``) and
    native OpenAI (which uses standard ``ChatOpenAI`` with ``reasoning_effort``).
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
        """Restore reasoning_content and thought_signature on historical messages.

        Uses DeerFlow's ``restore_assistant_payloads`` which handles length
        mismatches between payload and original messages via content +
        tool_call signature matching — no positional alignment assumption.
        """
        original_messages = self._convert_input(input_).to_messages()
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        payload_messages = payload.get("messages", [])

        # Replay reasoning_content (DashScope, Qwen, StepFun, etc.)
        restore_assistant_payloads(
            payload_messages, original_messages, restore_reasoning_content
        )

        # Replay thought_signature (Gemini via OpenAI gateway)
        restore_assistant_payloads(
            payload_messages, original_messages, _restore_tool_call_signatures
        )

        return payload

    # --- Streaming reasoning capture ---

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """Capture reasoning fields from streaming deltas."""
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
        """Extract reasoning fields from non-streaming responses."""
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
