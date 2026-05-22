"""Effective config builder — merges DB + files into DeerFlow2-compatible config.

Per-request config construction. No global singleton mutation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from packages.core.logging import get_logger
from packages.core.model_entry import build_model_entry
from packages.core.path_manager import PathManager

logger = get_logger(__name__)


@dataclass
class EffectiveConfig:
    """Result of EffectiveConfigBuilder.build()."""
    config_dict: dict[str, Any]
    skill_sources: list[dict[str, Any]] = field(default_factory=list)
    memory_path: str = ""


class EffectiveConfigBuilder:
    """Merge DB + builtin + tenant → DeerFlow2 config dict.

    Each call to build() produces an independent config.
    """

    def __init__(self, path_manager: PathManager):
        self._pm = path_manager

    def build(
        self,
        family_id: int,
        agent_name: str,
        ai_provider: dict[str, Any],
        agent_config: dict[str, Any],
        enabled_skills: list[dict[str, Any]],
        mcp_servers: list[dict[str, Any]],
    ) -> EffectiveConfig:
        model_entry = build_model_entry(ai_provider)

        memory_path = str(self._pm.tenant_memory_dir(family_id, agent_name) / "memory.json")
        skills_path = str(self._pm.effective_skills_dir(family_id))
        checkpointer_path = str(self._pm.db_dir / "deerflow-checkpoints.db")

        skill_sources = self._resolve_skill_sources(family_id, enabled_skills)

        config_dict: dict[str, Any] = {
            "models": [model_entry],
            "skills": {"path": skills_path},
            "memory": {"enabled": True, "storage_path": memory_path},
            "checkpointer": {"type": "sqlite", "connection_string": checkpointer_path},
        }

        if mcp_servers:
            config_dict["mcp_servers"] = mcp_servers

        return EffectiveConfig(
            config_dict=config_dict,
            skill_sources=skill_sources,
            memory_path=memory_path,
        )

    def _resolve_skill_sources(
        self, family_id: int, enabled_skills: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for skill in enabled_skills:
            name = skill["skill_name"]
            is_builtin = skill.get("is_builtin", False)
            if is_builtin:
                source = self._pm.builtin_skill_dir(name)
            else:
                source = self._pm.tenant_skill_dir(family_id, name)
            sources.append({"name": name, "source": source, "is_builtin": is_builtin})
        return sources
