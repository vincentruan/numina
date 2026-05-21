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
    ) -> AsyncGenerator:
        """Implemented in Task 8 — orchestrator integration."""
        raise NotImplementedError("stream() implemented in Task 8")
        yield  # make it a generator


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a markdown string, return body only."""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
