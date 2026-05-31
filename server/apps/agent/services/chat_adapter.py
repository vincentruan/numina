"""ChatAdapter — encapsulates chat-specific concerns.

Responsibilities:
- Load chat system prompt (family override → default fallback)
- Compose MCP SSE URL with family_id in path
- Stream events via DeerFlow with MCP server injected (Task 8)

Does NOT handle:
- Auth, policy, audit, journal, PII (orchestrator's responsibility)
"""
import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.adapter import (
    StreamChunk,
)
from apps.agent.services.deerflow_adapter.adapter import (
    create_family_adapter as _create_family_adapter,
)

logger = logging.getLogger(__name__)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / "chat"


class ChatAdapter:
    def __init__(self, backend_base_url: str, internal_token: str) -> None:
        self._backend_base_url = backend_base_url.rstrip("/")
        self._internal_token = internal_token

    def _mcp_url(self, family_id: str) -> str:
        if not _SAFE_ID_PATTERN.match(family_id):
            raise ValueError(f"Invalid family_id: {family_id!r}")
        return f"{self._backend_base_url}/api/v1/internal/mcp/{family_id}/sse"

    def _load_default_prompt(self) -> str:
        path = _PROMPT_DIR / "default_system_prompt.md"
        raw = path.read_text(encoding="utf-8")
        return _strip_frontmatter(raw)

    async def _fetch_family_prompt(self, family_id: str) -> str | None:
        """Fetch family's custom chat prompt from backend internal API."""
        url = f"{self._backend_base_url}/api/v1/internal/prompts/{family_id}/chat"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={
                    "X-Agent-Token": self._internal_token,
                    "X-Family-Id": family_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            # Backend uses envelope response: {code, data: {content: ...}, message}
            inner = data.get("data", data)
            return inner.get("content")

    async def _resolve_prompt(self, family_id: str) -> str:
        """Load family override → default fallback."""
        try:
            override = await self._fetch_family_prompt(family_id)
            if override:
                return override
        except Exception as e:
            logger.warning("[chat_adapter] fetch family prompt failed family=%s: %s", family_id, e)
        return self._load_default_prompt()

    async def stream(
        self,
        family_id: str,
        question: str,
        thread_id: str,
        ai_config: dict[str, Any],
        deep_think: bool = False,
        web_search: bool = False,
        enable_thinking: bool = False,
        caller_user_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat response via DeerFlow with family MCP server injected.

        system_prompt is prepended to the user question in free_text because
        DeerFlow has no separate system_prompt config key — the skill file body
        and the message content are the only injection points available.
        """
        system_prompt = await self._resolve_prompt(family_id)
        # Append web_search behavioral guidance so the LLM knows whether it may search
        if web_search:
            system_prompt += "\n\n## 联网搜索\n\n用户已启用联网搜索。如果需要最新信息，你可以调用搜索工具获取。"
        else:
            system_prompt += "\n\n## 联网搜索\n\n用户未启用联网搜索。请仅基于已有工具和知识回答，不要尝试联网。"
        mcp_headers: dict[str, str] = {
            "X-Agent-Token": self._internal_token,
            "X-Family-Id": family_id,
        }
        if caller_user_id:
            mcp_headers["X-Caller-User-Id"] = caller_user_id
        mcp_servers = [
            {
                "name": "numina-family-data",
                "url": self._mcp_url(family_id),
                "transport": "sse",
                "headers": mcp_headers,
            }
        ]

        adapter = _create_family_adapter(
            family_id=family_id,
            ai_config=ai_config,
            timeout_seconds=int(ai_config.get("timeout_seconds", 60)),
            subagent_enabled=deep_think,
            plan_mode=deep_think,
            mcp_servers=mcp_servers,
        )

        # Wrap system_prompt and question in XML tags for structural separation.
        # DeerFlow has no separate system_prompt config key; this is the cleanest
        # injection point. XML tags give the LLM clear authority boundaries.
        augmented_text = (
            f"<system_instructions>\n{system_prompt}\n</system_instructions>\n\n"
            f"<user_question>\n{question}\n</user_question>"
        )
        context = RedactedContext(family_id=family_id, free_text=augmented_text)

        skill_name = "chat-search" if web_search else "chat"
        async for chunk in adapter.stream_dispatch(
            skill_name,
            context,
            thread_id,
            enable_thinking=enable_thinking or deep_think,
        ):
            yield chunk


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a markdown string, return body only."""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
