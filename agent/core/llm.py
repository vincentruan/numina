"""统一 LLM 调用封装（Anthropic / OpenAI）。"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
        self._anthropic_client = None
        self._openai_client = None
        if provider == "anthropic":
            import anthropic
            kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._anthropic_client = anthropic.AsyncAnthropic(**kwargs)
        elif provider == "openai":
            from openai import AsyncOpenAI
            kwargs = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._openai_client = AsyncOpenAI(**kwargs)

    async def complete(self, prompt: str, max_tokens: int = 512, system: str | None = None) -> str:
        """发送单次补全请求，返回文本响应。"""
        if self.provider == "anthropic":
            return await self._complete_anthropic(prompt, max_tokens, system)
        elif self.provider == "openai":
            return await self._complete_openai(prompt, max_tokens, system)
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def stream_text(self, prompt: str, max_tokens: int = 1024, system: str | None = None):
        """流式输出纯文本（不开启 thinking）。Yields text chunks."""
        if self.provider == "anthropic":
            async for chunk in self._stream_anthropic_text(prompt, max_tokens, system):
                yield chunk
        elif self.provider == "openai":
            async for _, chunk in self._stream_openai_thinking(prompt, max_tokens, system, enable_thinking=False):
                yield chunk

    async def stream_with_thinking(self, prompt: str, max_tokens: int = 8000, system: str | None = None, thinking_budget: int = 5000):
        """流式输出，支持 extended_thinking。
        Yields (block_type, text_chunk) where block_type is 'thinking' or 'text'.
        - Anthropic: uses native extended_thinking blocks
        - OpenAI-compatible: reads reasoning_content field, falls back to <think> tag parsing
        """
        if self.provider == "anthropic":
            async for item in self._stream_anthropic_thinking(prompt, max_tokens, system, thinking_budget):
                yield item
        else:
            async for item in self._stream_openai_thinking(prompt, max_tokens, system, enable_thinking=True):
                yield item

    async def _stream_anthropic_text(self, prompt: str, max_tokens: int, system: str | None):
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
                    delta = event.delta
                    if getattr(delta, "type", None) == "text_delta":
                        yield delta.text

    async def _stream_anthropic_thinking(self, prompt: str, max_tokens: int, system: str | None, thinking_budget: int):
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
                    delta = event.delta
                    delta_type = getattr(delta, "type", None)
                    if delta_type == "thinking_delta":
                        yield ("thinking", delta.thinking)
                    elif delta_type == "text_delta":
                        yield ("text", delta.text)

    async def _stream_openai_thinking(self, prompt: str, max_tokens: int, system: str | None, enable_thinking: bool = False):
        """OpenAI-compatible streaming with optional thinking support.

        Yields (block_type, chunk) tuples where block_type is 'thinking' or 'text'.
        Handles two thinking formats:
        - reasoning_content field (DeepSeek-R1, Qwen3 via API)
        - <think>...</think> tags embedded in content (self-hosted vLLM/Ollama)
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
        }
        if enable_thinking:
            kwargs["extra_body"] = {"enable_thinking": True}

        stream = await self._openai_client.chat.completions.create(**kwargs)

        # Track whether we're inside a <think> tag for tag-based fallback
        in_think_tag = False
        tag_buffer = ""  # accumulates partial tag text to detect opening/closing

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

            # Parse <think>...</think> tags embedded in content stream
            tag_buffer += text
            while tag_buffer:
                if not in_think_tag:
                    think_start = tag_buffer.find("<think>")
                    if think_start == -1:
                        # No opening tag — check if we might be mid-tag at the end
                        # Emit everything except the last 6 chars (len("<think>") - 1)
                        safe_end = max(0, len(tag_buffer) - 6)
                        if safe_end > 0:
                            yield ("text", tag_buffer[:safe_end])
                            tag_buffer = tag_buffer[safe_end:]
                        break
                    else:
                        if think_start > 0:
                            yield ("text", tag_buffer[:think_start])
                        tag_buffer = tag_buffer[think_start + len("<think>"):]
                        in_think_tag = True
                else:
                    think_end = tag_buffer.find("</think>")
                    if think_end == -1:
                        # Still inside think block — emit all but last 8 chars
                        safe_end = max(0, len(tag_buffer) - 8)
                        if safe_end > 0:
                            yield ("thinking", tag_buffer[:safe_end])
                            tag_buffer = tag_buffer[safe_end:]
                        break
                    else:
                        if think_end > 0:
                            yield ("thinking", tag_buffer[:think_end])
                        tag_buffer = tag_buffer[think_end + len("</think>"):]
                        in_think_tag = False

        # Flush remaining buffer
        if tag_buffer:
            yield ("thinking" if in_think_tag else "text", tag_buffer)

    async def complete_vision(self, prompt: str, image_data: str, max_tokens: int = 512, system: str | None = None) -> str:
        """发送图像理解请求，返回文本响应。使用 vision_model_id。"""
        if self.provider == "anthropic":
            return await self._complete_anthropic_vision(prompt, image_data, max_tokens, system)
        elif self.provider == "openai":
            return await self._complete_openai_vision(prompt, image_data, max_tokens, system)
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def _complete_anthropic(self, prompt: str, max_tokens: int, system: str | None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        message = await self._anthropic_client.messages.create(**kwargs)
        # Skip ThinkingBlock entries; find the first TextBlock
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    async def _complete_openai(self, prompt: str, max_tokens: int, system: str | None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self._openai_client.chat.completions.create(
            model=self.model_id,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    async def _complete_anthropic_vision(self, prompt: str, image_data: str, max_tokens: int, system: str | None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.vision_model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                {"type": "text", "text": prompt},
            ]}],
        }
        if system:
            kwargs["system"] = system
        message = await self._anthropic_client.messages.create(**kwargs)
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    async def _complete_openai_vision(self, prompt: str, image_data: str, max_tokens: int, system: str | None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
            {"type": "text", "text": prompt},
        ]})
        response = await self._openai_client.chat.completions.create(
            model=self.vision_model_id,
            max_tokens=max_tokens,
            messages=messages,
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
    return LLMClient(provider=provider, api_key=api_key, model_id=model_id, vision_model_id=vision_model_id, base_url=base_url, timeout=timeout)
