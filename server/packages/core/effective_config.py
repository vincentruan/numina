"""Effective config builder — merges DB + files into DeerFlow2-compatible config.

Per-request config construction. No global singleton mutation.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
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
    extensions_config_path: str = ""  # Path to generated extensions_config.json


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

        # Materialize skill sources into effective_skills_dir so DeerFlow can load them.
        self._materialize_skills(family_id, skill_sources)

        config_dict: dict[str, Any] = {
            "models": [model_entry],
            "skills": {"path": skills_path},
            "memory": {"enabled": True, "storage_path": memory_path},
            "checkpointer": {"type": "sqlite", "connection_string": checkpointer_path},
        }

        # DeerFlow reads MCP servers from extensions_config.json (not config.yaml).
        # Generate the file and return its path so the caller can set DEER_FLOW_EXTENSIONS_CONFIG_PATH.
        extensions_config_path = ""
        if mcp_servers:
            extensions_config_path = self._generate_extensions_config(mcp_servers)

        return EffectiveConfig(
            config_dict=config_dict,
            skill_sources=skill_sources,
            memory_path=memory_path,
            extensions_config_path=extensions_config_path,
        )

    def _generate_extensions_config(self, mcp_servers: list[dict[str, Any]]) -> str:
        """Generate extensions_config.json for DeerFlow's MCP tool loading.

        DeerFlow reads MCP server configs from extensions_config.json via
        the DEER_FLOW_EXTENSIONS_CONFIG_PATH environment variable.

        Args:
            mcp_servers: List of MCP server configs from backend API.

        Returns:
            Path to the generated extensions_config.json file.
        """
        mcp_servers_dict: dict[str, Any] = {}
        for srv in mcp_servers:
            name = srv.get("name", "default")
            mcp_servers_dict[name] = {
                "type": srv.get("transport", "sse"),
                "url": srv.get("url", ""),
                "headers": srv.get("headers", {}),
                "enabled": True,
            }

        extensions_data = {"mcpServers": mcp_servers_dict}

        # Write to a temp file that will be cleaned up after the request.
        temp_dir = Path(tempfile.mkdtemp(prefix="deerflow_extensions_"))
        extensions_path = temp_dir / "extensions_config.json"
        with open(extensions_path, "w", encoding="utf-8") as f:
            json.dump(extensions_data, f, ensure_ascii=False)

        logger.debug(
            "[effective_config] generated extensions_config.json at %s with %s MCP servers",
            extensions_path,
            len(mcp_servers_dict),
        )
        return str(extensions_path)

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

    def _materialize_skills(
        self, family_id: int, skill_sources: list[dict[str, Any]]
    ) -> None:
        """Symlink resolved skill sources into effective_skills_dir.

        DeerFlow reads skills from a single directory (config_dict["skills"]["path"]).
        This method creates symlinks from each skill source into that directory
        so DeerFlow can discover them at runtime.
        """
        target_dir = self._pm.effective_skills_dir(family_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Clean stale symlinks that no longer correspond to enabled skills.
        enabled_names = {s["name"] for s in skill_sources}
        for entry in target_dir.iterdir():
            if entry.is_symlink() and entry.name not in enabled_names:
                entry.unlink()

        for skill in skill_sources:
            link_path = target_dir / skill["name"]
            source_path = Path(str(skill["source"]))

            if link_path.exists() or link_path.is_symlink():
                # Already linked — verify target matches.
                if link_path.is_symlink() and link_path.resolve() == source_path.resolve():
                    continue
                link_path.unlink()

            if source_path.exists():
                os.symlink(source_path, link_path)
            else:
                logger.warning(
                    "[effective_config] skill source not found: %s", source_path
                )
