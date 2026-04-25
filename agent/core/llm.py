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
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.vision_model_id = vision_model_id or model_id
        self._anthropic_client = None
        self._openai_client = None
        if provider == "anthropic":
            import anthropic
            kwargs: dict[str, Any] = {"api_key": api_key, "timeout": 30.0}
            if base_url:
                kwargs["base_url"] = base_url
            self._anthropic_client = anthropic.AsyncAnthropic(**kwargs)
        elif provider == "openai":
            from openai import AsyncOpenAI
            kwargs = {"api_key": api_key, "timeout": 30.0}
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
) -> LLMClient:
    """工厂函数，创建 LLM 客户端实例。"""
    return LLMClient(provider=provider, api_key=api_key, model_id=model_id, vision_model_id=vision_model_id, base_url=base_url)
