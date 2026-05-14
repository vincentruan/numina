"""Capability registry backed by DeerFlow skill definitions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from apps.agent.schemas.capability import (
    CapabilityDefinition,
    CapabilityPolicy,
    CapabilityUISchema,
)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


class CapabilityRegistry:
    """Loads capabilities from agent skill frontmatter."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        self._capabilities: dict[str, CapabilityDefinition] | None = None

    def list_capabilities(self) -> list[CapabilityDefinition]:
        if self._capabilities is None:
            self._capabilities = self._load()
        return list(self._capabilities.values())

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        if self._capabilities is None:
            self._capabilities = self._load()
        return self._capabilities.get(capability_id)

    def _load(self) -> dict[str, CapabilityDefinition]:
        capabilities: dict[str, CapabilityDefinition] = {}
        for skill_file in sorted(self.skills_dir.glob("*.md")):
            meta = self._read_frontmatter(skill_file)
            capability_id = str(meta.get("capability") or skill_file.stem)
            capabilities[capability_id] = CapabilityDefinition(
                id=capability_id,
                name=str(meta.get("name") or capability_id),
                description=str(meta.get("description") or ""),
                category=str(meta.get("category") or "general"),
                ui=CapabilityUISchema(
                    icon=str(meta.get("icon") or "message-circle"),
                    color=str(meta.get("color") or "#6366f1"),
                    route=meta.get("route"),
                    input_mode=str(meta.get("input_mode") or "free_text"),
                    placeholder=meta.get("placeholder"),
                    example_questions=list(meta.get("examples") or []),
                ),
                policy=CapabilityPolicy(
                    allowed_roles=list(meta.get("allowed_roles") or ["member", "admin"]),
                    require_confirmation=bool(meta.get("require_confirmation", False)),
                    max_tokens=int(meta.get("max_tokens") or 2000),
                    enable_thinking=bool(meta.get("thinking", True)),
                    enable_tools=list(meta.get("mcp_tools") or []),
                ),
                skill_id=capability_id,
                harness_config=dict(meta.get("harness") or {}),
            )
        return capabilities

    def _read_frontmatter(self, skill_file: Path) -> dict[str, Any]:
        content = skill_file.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return {"capability": skill_file.stem}
        parsed = yaml.safe_load(match.group(1)) or {}
        return parsed if isinstance(parsed, dict) else {"capability": skill_file.stem}


capability_registry = CapabilityRegistry()
