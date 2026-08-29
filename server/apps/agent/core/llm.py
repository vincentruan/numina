"""统一 LLM 调用封装（Anthropic / OpenAI）。"""

import logging
from collections.abc import Iterator
from typing import Any, cast

logger = logging.getLogger(__name__)


def _is_unsupported_response_format_error(exc: Exception) -> bool:
    """Check if an exception indicates the model doesn't support response_format.

    Some OpenAI-compatible providers/models return 400 when response_format is
    set but not supported. Detect by status code + error message patterns.
    """
    error_str = str(exc).lower()
    # Check for HTTP 400 status
    has_400 = "400" in error_str or "bad request" in error_str
    # Check for response_format-related messages
    has_rf_hint = any(
        kw in error_str
        for kw in ("response_format", "json_object", "structured output", "not supported")
    )
    return has_400 and has_rf_hint


class LLMResponseError(Exception):
    """LLM 返回无效/空响应时抛出。

    用于标准化错误处理，区分：
    - API 连接错误（由 SDK 抛出）
    - API 返回格式错误（由此异常抛出）
    """

    def __init__(self, provider: str, message: str, details: str | None = None):
        self.provider = provider
        self.message = message
        self.details = details
        super().__init__(
            f"[{provider}] {message}: {details}"
            if details
            else f"[{provider}] {message}"
        )


class ThinkingTagParser:
    """解析 OpenAI-compatible 流式响应中的 thinking 标签。

    处理两种 thinking 格式：
    - reasoning_content 字段（DeepSeek-R1, Qwen3 API）
    - ... tags 嵌入在 content 中（self-hosted vLLM/Ollama）

    Buffer size limit 防止 malformed tags 导致内存泄漏。
    """

    MAX_BUFFER_SIZE = 10000  # ~10KB, prevents malformed tag memory bloat
    _OPEN_TAG = "<think>"
    _CLOSE_TAG = "</think>"

    def __init__(self):
        self.buffer = ""
        self.in_think_tag = False

    def feed(self, text: str) -> Iterator[tuple[str, str]]:
        """Feed text chunk and yield (block_type, content) tuples.

        Args:
            text: Text chunk from stream

        Yields:
            (block_type, content) where block_type is 'thinking' or 'text'
        """
        self.buffer += text

        # Safety limit: if buffer grows beyond MAX, emit as text
        if len(self.buffer) > self.MAX_BUFFER_SIZE:
            # Find last complete tag boundary if possible
            safe_boundary = self.buffer.rfind(self._CLOSE_TAG)
            if safe_boundary > self.MAX_BUFFER_SIZE - 100:
                # Emit up to boundary, preserve tag structure
                yield ("thinking", self.buffer[:safe_boundary])
                self.buffer = self.buffer[safe_boundary:]
            else:
                # Force emit with warning
                logger.warning(
                    "Thinking tag buffer overflow at %d chars, output may be corrupted",
                    len(self.buffer),
                )
                yield ("text", self.buffer[: self.MAX_BUFFER_SIZE])
                self.buffer = self.buffer[self.MAX_BUFFER_SIZE :]
                self.in_think_tag = False

        while self.buffer:
            if not self.in_think_tag:
                think_start = self.buffer.find(self._OPEN_TAG)
                if think_start == -1:
                    # No opening tag — check if we might be mid-tag at the end
                    # Emit everything except the last len(_OPEN_TAG)-1 chars
                    safe_end = max(0, len(self.buffer) - (len(self._OPEN_TAG) - 1))
                    if safe_end > 0:
                        yield ("text", self.buffer[:safe_end])
                        self.buffer = self.buffer[safe_end:]
                    break
                else:
                    if think_start > 0:
                        yield ("text", self.buffer[:think_start])
                    self.buffer = self.buffer[think_start + len(self._OPEN_TAG) :]
                    self.in_think_tag = True
            else:
                think_end = self.buffer.find(self._CLOSE_TAG)
                if think_end == -1:
                    # Still inside think block — emit all but last len(_CLOSE_TAG)-1 chars
                    safe_end = max(0, len(self.buffer) - (len(self._CLOSE_TAG) - 1))
                    if safe_end > 0:
                        yield ("thinking", self.buffer[:safe_end])
                        self.buffer = self.buffer[safe_end:]
                    break
                else:
                    if think_end > 0:
                        yield ("thinking", self.buffer[:think_end])
                    self.buffer = self.buffer[think_end + len(self._CLOSE_TAG) :]
                    self.in_think_tag = False

    def flush(self) -> tuple[str, str] | None:
        """Flush remaining buffer.

        Returns:
            (block_type, content) if buffer non-empty, else None
        """
        if self.buffer:
            result = ("thinking" if self.in_think_tag else "text", self.buffer)
            self.buffer = ""
            return result
        return None


class LLMClient:
    """统一 LLM 调用接口，支持 Anthropic 和 OpenAI。"""

    def __init__(
        self,
        provider: str,
        api_key: str,
        model_id: str,
        vision_model_id: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.vision_model_id = vision_model_id or model_id
        self._api_key = api_key
        self._base_url = base_url
        self._anthropic_client = None
        self._openai_client = None
        if provider == "anthropic":
            import anthropic

            kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._anthropic_client = anthropic.AsyncAnthropic(**kwargs)
        elif provider in ("openai", "openai_compatible"):
            from openai import AsyncOpenAI

            kwargs = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._openai_client = AsyncOpenAI(**kwargs)

    async def complete(
        self, prompt: str, max_tokens: int = 512, system: str | None = None
    ) -> str:
        """发送单次补全请求，返回文本响应。"""
        if self.provider == "anthropic":
            return await self._complete_anthropic(prompt, max_tokens, system)
        elif self.provider in ("openai", "openai_compatible"):
            return await self._complete_openai(prompt, max_tokens, system)
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def complete_json(
        self,
        prompt: str,
        max_tokens: int = 4000,
        system: str | None = None,
    ) -> str:
        """Send a completion request with JSON output enforcement.

        For OpenAI-compatible providers: sets ``response_format={"type": "json_object"}``
        so the API guarantees valid JSON output (no markdown fences, no prose).
        Falls back to plain ``complete()`` if the model doesn't support response_format
        (400 error from the API).

        For Anthropic: no native JSON mode — adds a system hint instead.
        The caller should still use ``parse_report_json`` for tolerant parsing.
        """
        if self.provider == "anthropic":
            # Anthropic has no response_format — use system hint
            json_system = (
                "You are a structured data extractor. "
                "Output ONLY valid JSON. No markdown, no prose, no code fences."
            )
            combined_system = (
                f"{json_system}\n{system}" if system else json_system
            )
            return await self._complete_anthropic(
                prompt, max_tokens, combined_system
            )
        elif self.provider in ("openai", "openai_compatible"):
            try:
                return await self._complete_openai(
                    prompt, max_tokens, system, response_format="json_object"
                )
            except Exception as exc:
                # Some models don't support response_format — fallback to plain
                # completion. Caller still uses parse_report_json for tolerance.
                if _is_unsupported_response_format_error(exc):
                    logger.warning(
                        "[complete_json] response_format not supported by model %s, "
                        "falling back to plain complete: %s",
                        self.model_id,
                        exc,
                    )
                    return await self._complete_openai(prompt, max_tokens, system)
                raise
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def stream_text(
        self, prompt: str, max_tokens: int = 1024, system: str | None = None
    ):
        """流式输出纯文本（不开启 thinking）。Yields text chunks."""
        if self.provider == "anthropic":
            async for chunk in self._stream_anthropic_text(prompt, max_tokens, system):
                yield chunk
        elif self.provider in ("openai", "openai_compatible"):
            async for _, chunk in self._stream_openai_thinking(
                prompt, max_tokens, system, enable_thinking=False
            ):
                yield chunk

    async def stream_with_thinking(
        self,
        prompt: str,
        max_tokens: int = 8000,
        system: str | None = None,
        thinking_budget: int = 5000,
    ):
        """流式输出，支持 extended_thinking。
        Yields (block_type, text_chunk) where block_type is 'thinking' or 'text'.
        - Anthropic: uses native extended_thinking blocks
        - OpenAI-compatible: reads reasoning_content field, falls back to  tag parsing
        """
        if self.provider == "anthropic":
            async for item in self._stream_anthropic_thinking(
                prompt, max_tokens, system, thinking_budget
            ):
                yield item
        else:
            async for item in self._stream_openai_thinking(
                prompt, max_tokens, system, enable_thinking=True
            ):
                yield item

    async def _stream_anthropic_text(
        self, prompt: str, max_tokens: int, system: str | None
    ):
        assert self._anthropic_client is not None
        kwargs: dict = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        async with self._anthropic_client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if type(event).__name__ == "ContentBlockDeltaEvent":
                    delta = getattr(event, "delta", None)
                    if delta is not None and getattr(delta, "type", None) == "text_delta":
                        yield delta.text

    async def _stream_anthropic_thinking(
        self, prompt: str, max_tokens: int, system: str | None, thinking_budget: int
    ):
        assert self._anthropic_client is not None
        kwargs: dict = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        async with self._anthropic_client.messages.stream(**kwargs) as stream:
            async for event in stream:
                event_type = type(event).__name__
                if event_type == "ContentBlockDeltaEvent":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    delta_type = getattr(delta, "type", None)
                    if delta_type == "thinking_delta":
                        yield ("thinking", delta.thinking)
                    elif delta_type == "text_delta":
                        yield ("text", delta.text)

    async def _stream_openai_thinking(
        self,
        prompt: str,
        max_tokens: int,
        system: str | None,
        enable_thinking: bool = False,
    ):
        """OpenAI-compatible streaming with optional thinking support.

        Yields (block_type, chunk) tuples where block_type is 'thinking' or 'text'.
        Handles two thinking formats:
        - reasoning_content field (DeepSeek-R1, Qwen3 via API)
        - ... tags embedded in content (self-hosted vLLM/Ollama)
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
            "extra_body": {"enable_thinking": enable_thinking},
        }

        assert self._openai_client is not None
        stream = await self._openai_client.chat.completions.create(**kwargs)

        # Use dedicated parser class for tag-based thinking extraction
        parser = ThinkingTagParser()

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # reasoning_content field (DeepSeek-R1, Qwen3 API)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield ("thinking", reasoning)
                continue

            text = delta.content or ""
            if not text:
                continue

            if not enable_thinking:
                yield ("text", text)
                continue

            # Parse ... tags using dedicated parser
            for block_type, content in parser.feed(text):
                yield (block_type, content)

        # Flush remaining buffer
        final = parser.flush()
        if final:
            yield final

    async def complete_vision(
        self,
        prompt: str,
        image_data: str,
        max_tokens: int = 512,
        system: str | None = None,
    ) -> str:
        """发送图像理解请求，返回文本响应。使用 vision_model_id。"""
        if self.provider == "anthropic":
            return await self._complete_anthropic_vision(
                prompt, image_data, max_tokens, system
            )
        elif self.provider in ("openai", "openai_compatible"):
            return await self._complete_openai_vision(
                prompt, image_data, max_tokens, system
            )
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def _complete_anthropic(
        self, prompt: str, max_tokens: int, system: str | None
    ) -> str:
        """Anthropic 单次补全请求。

        Raises:
            LLMResponseError: 响应无文本块
        """
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        assert self._anthropic_client is not None
        message = await self._anthropic_client.messages.create(**kwargs)
        # Skip ThinkingBlock entries; find the first TextBlock
        for block in message.content:
            text = cast(str, getattr(block, "text", None))
            if text is not None:
                return text
        # DeepSeek / non-Anthropic models routed through Anthropic SDK may
        # return only ThinkingBlock when max_tokens is too low to leave
        # budget for a TextBlock (reasoning is intrinsic to the model).
        # Treat thinking content as valid connection proof (see Qwen3
        # enable_thinking empty content pattern).
        for block in message.content:
            thinking = cast(str, getattr(block, "thinking", None))
            if thinking is not None:
                return thinking
        # 标准化错误处理：明确告知响应格式问题
        block_types = [type(b).__name__ for b in message.content]
        raise LLMResponseError(
            provider="anthropic",
            message="Response contains no text or thinking blocks",
            details=f"block_types={block_types}, model={self.model_id}",
        )

    async def _complete_openai(
        self,
        prompt: str,
        max_tokens: int,
        system: str | None,
        response_format: str | None = None,
    ) -> str:
        """OpenAI 单次补全请求。

        Args:
            response_format: If ``"json_object"``, sets OpenAI's response_format
                to guarantee valid JSON output. Only effective for models that
                support structured output (GPT-4o, GPT-4o-mini, etc.).

        Raises:
            LLMResponseError: 响应为空或无内容
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        assert self._openai_client is not None
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": cast(Any, messages),
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._openai_client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content:
            return content

        # DeepSeek / Qwen3 等 reasoning 模型在 max_tokens 较小时可能只输出
        # reasoning_content 而 content 为空。把 reasoning_content 视为有效响应，
        # 避免连接测试误报失败。
        reasoning_content = getattr(
            response.choices[0].message, "reasoning_content", None
        )
        if reasoning_content:
            return cast(str, reasoning_content)

        # 标准化错误处理：明确告知响应为空
        raise LLMResponseError(
            provider="openai",
            message="Response content is empty",
            details=f"model={self.model_id}, finish_reason={response.choices[0].finish_reason}",
        )

    async def _complete_anthropic_vision(
        self, prompt: str, image_data: str, max_tokens: int, system: str | None
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.vision_model_id,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        if system:
            kwargs["system"] = system
        assert self._anthropic_client is not None
        message = await self._anthropic_client.messages.create(**kwargs)
        for block in message.content:
            text = cast(str, getattr(block, "text", None))
            if text is not None:
                return text
        # Same fallback as _complete_anthropic: DeepSeek / non-Anthropic
        # models may return only ThinkingBlock when max_tokens is too low.
        for block in message.content:
            thinking = cast(str, getattr(block, "thinking", None))
            if thinking is not None:
                return thinking
        return ""

    async def _complete_openai_vision(
        self, prompt: str, image_data: str, max_tokens: int, system: str | None
    ) -> str:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        )
        assert self._openai_client is not None
        response = await self._openai_client.chat.completions.create(
            model=self.vision_model_id,
            max_tokens=max_tokens,
            messages=cast(Any, messages),
        )
        return response.choices[0].message.content or ""


def get_llm_client(
    provider: str,
    api_key: str,
    model_id: str,
    vision_model_id: str | None = None,
    base_url: str | None = None,
    timeout: float = 60.0,
) -> LLMClient:
    """工厂函数，创建 LLM 客户端实例。"""
    return LLMClient(
        provider=provider,
        api_key=api_key,
        model_id=model_id,
        vision_model_id=vision_model_id,
        base_url=base_url,
        timeout=timeout,
    )
