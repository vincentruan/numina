"""统一 LLM 调用封装（Anthropic / OpenAI）。"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient:
    """统一 LLM 调用接口，支持 Anthropic 和 OpenAI。"""

    def __init__(self, provider: str, api_key: str) -> None:
        self.provider = provider
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 512, system: str | None = None) -> str:
        """发送单次补全请求，返回文本响应。"""
        if self.provider == "anthropic":
            return await self._complete_anthropic(prompt, max_tokens, system)
        elif self.provider == "openai":
            return await self._complete_openai(prompt, max_tokens, system)
        else:
            raise ValueError(f"不支持的 LLM Provider: {self.provider}")

    async def _complete_anthropic(self, prompt: str, max_tokens: int, system: str | None) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        kwargs: dict[str, Any] = {
            "model": "claude-haiku-4-5",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = await client.messages.create(**kwargs)
        return message.content[0].text

    async def _complete_openai(self, prompt: str, max_tokens: int, system: str | None) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""


def get_llm_client(provider: str, api_key: str) -> LLMClient:
    """工厂函数，创建 LLM 客户端实例。"""
    return LLMClient(provider=provider, api_key=api_key)
