"""SkillLoader — 从 agent/skills/{capability}.md 加载 prompt 和元数据。"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)


@dataclass
class SkillConfig:
    capability: str
    prompt: str
    thinking: bool = True
    mcp_tools: list[str] = field(default_factory=list)


class SkillLoader:
    """Loads skill configs from Markdown files with YAML frontmatter."""

    def __init__(self) -> None:
        self._cache: dict[str, SkillConfig] = {}

    def load(self, capability: str) -> SkillConfig:
        if capability in self._cache:
            return self._cache[capability]

        path = SKILLS_DIR / f"{capability}.md"
        if not path.exists():
            # Return a minimal config if skill file not found
            return SkillConfig(capability=capability, prompt="", thinking=False)

        content = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return SkillConfig(capability=capability, prompt=content.strip(), thinking=False)

        frontmatter_str, body = match.group(1), match.group(2).strip()
        try:
            meta = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            meta = {}

        config = SkillConfig(
            capability=capability,
            prompt=body,
            thinking=bool(meta.get("thinking", True)),
            mcp_tools=list(meta.get("mcp_tools", [])),
        )
        self._cache[capability] = config
        return config

    def get_prompt(self, capability: str) -> str:
        return self.load(capability).prompt

    def thinking_enabled(self, capability: str) -> bool:
        return self.load(capability).thinking

    def invalidate(self, capability: str | None = None) -> None:
        """Clear cache for a specific capability or all."""
        if capability:
            self._cache.pop(capability, None)
        else:
            self._cache.clear()


skill_loader = SkillLoader()
