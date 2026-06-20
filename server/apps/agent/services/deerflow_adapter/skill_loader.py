"""SkillLoader — 从 agent/skills/{capability}.md 加载 prompt 和元数据。

支持 per-family prompt 覆盖：
- 调用 load_for_family(capability, family_id) 时，先查询后端 /ai/skills/{capability}
  获取家庭自定义 prompt（若有），并按 (family_id, capability, updated_at) 缓存。
- 默认 load(capability) 行为不变（全局文件缓存）。
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
import yaml

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)

logger = logging.getLogger(__name__)


@dataclass
class SkillConfig:
    capability: str
    prompt: str
    thinking: bool = True
    mcp_tools: list[str] = field(default_factory=list)
    is_enabled: bool = True
    subagent_enabled: bool = False
    plan_mode: bool = False


@dataclass
class _FamilyPromptEntry:
    """Cache entry for a per-family prompt override."""
    prompt: str | None          # None means "use default"
    is_enabled: bool
    updated_at: datetime


class SkillLoader:
    """Loads skill configs from Markdown files with YAML frontmatter."""

    def __init__(self) -> None:
        self._cache: dict[str, SkillConfig] = {}
        # Key: (family_id, capability) → _FamilyPromptEntry
        self._family_cache: dict[tuple[str, str], _FamilyPromptEntry] = {}

    # ── File-based loading (unchanged) ────────────────────────────────────────

    def load(self, capability: str) -> SkillConfig:
        if capability in self._cache:
            return self._cache[capability]

        # New path: skills/builtin/{capability}/SKILL.md
        path = SKILLS_DIR / "builtin" / capability / "SKILL.md"
        if not path.exists():
            # Fallback old path: skills/{capability}.md
            path = SKILLS_DIR / f"{capability}.md"

        if not path.exists():
            return SkillConfig(capability=capability, prompt="", thinking=False)

        content = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return SkillConfig(capability=capability, prompt=content.strip(), thinking=False)

        frontmatter_str = match.group(1)
        try:
            meta = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            meta = {}

        config = SkillConfig(
            capability=capability,
            prompt="",  # prompts live in skills/custom/*/SKILL.md, loaded by DeerFlow harness
            thinking=bool(meta.get("thinking", True)),
            mcp_tools=list(meta.get("mcp_tools", [])),
            subagent_enabled=bool(meta.get("subagent_enabled", False)),
            plan_mode=bool(meta.get("plan_mode", False)),
        )
        self._cache[capability] = config
        return config

    def thinking_enabled(self, capability: str) -> bool:
        return self.load(capability).thinking

    # ── Per-family loading ────────────────────────────────────────────────────

    async def load_for_family(
        self,
        capability: str,
        family_id: str,
        backend_base_url: str,
        internal_token: str,
    ) -> SkillConfig:
        """Load skill config with per-family prompt override applied.

        Fetches family config from backend /ai/skills/{capability} and caches
        the result keyed by (family_id, capability, updated_at).  Falls back to
        the default file-based prompt on any error.
        """
        base = self.load(capability)

        try:
            entry = await self._fetch_family_entry(
                capability, family_id, backend_base_url, internal_token
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch family skill config family=%s capability=%s: %s",
                family_id, capability, exc,
            )
            return base

        if not entry.is_enabled:
            # Return config with empty prompt so orchestrator can skip/block
            return SkillConfig(
                capability=capability,
                prompt="",
                thinking=base.thinking,
                mcp_tools=base.mcp_tools,
                is_enabled=False,
                subagent_enabled=base.subagent_enabled,
                plan_mode=base.plan_mode,
            )

        effective_prompt = entry.prompt if entry.prompt else base.prompt
        return SkillConfig(
            capability=capability,
            prompt=effective_prompt,
            thinking=base.thinking,
            mcp_tools=base.mcp_tools,
            is_enabled=True,
            subagent_enabled=base.subagent_enabled,
            plan_mode=base.plan_mode,
        )

    async def _fetch_family_entry(
        self,
        capability: str,
        family_id: str,
        backend_base_url: str,
        internal_token: str,
    ) -> _FamilyPromptEntry:
        """Fetch and cache per-family skill config from backend.

        Cache key includes updated_at so stale entries are replaced automatically
        when the family updates their prompt.
        """
        url = f"{backend_base_url.rstrip('/')}/api/v1/ai/skills/{capability}"
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            resp = await client.get(
                url,
                headers={"X-Internal-Token": internal_token, "X-Family-Id": family_id},
            )
            resp.raise_for_status()
            data = resp.json()

        updated_at_raw = data.get("updated_at")
        # When updated_at is None the family has no custom config; use datetime.min
        # as a stable sentinel so the cache entry is reused across calls (no churn).
        # The entry will be replaced as soon as the family saves a custom prompt and
        # updated_at becomes a real timestamp.
        updated_at = (
            datetime.fromisoformat(updated_at_raw) if updated_at_raw else datetime.min
        )

        cache_key = (family_id, capability)
        cached = self._family_cache.get(cache_key)
        if cached and cached.updated_at == updated_at:
            return cached

        entry = _FamilyPromptEntry(
            prompt=data.get("custom_prompt"),
            is_enabled=data.get("is_enabled", True),
            updated_at=updated_at,
        )
        self._family_cache[cache_key] = entry
        return entry

    # ── Cache management ──────────────────────────────────────────────────────

    def invalidate(self, capability: str | None = None) -> None:
        """Clear file-based cache for a specific capability or all."""
        if capability:
            self._cache.pop(capability, None)
        else:
            self._cache.clear()

    def invalidate_family(self, family_id: str, capability: str | None = None) -> None:
        """Clear per-family cache entries."""
        if capability:
            self._family_cache.pop((family_id, capability), None)
        else:
            keys = [k for k in self._family_cache if k[0] == family_id]
            for k in keys:
                del self._family_cache[k]


skill_loader = SkillLoader()
