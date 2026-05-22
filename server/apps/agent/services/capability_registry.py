"""Capability registry backed by DeerFlow skill definitions."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import httpx
import yaml

from apps.agent.schemas.capability import (
    CapabilityDefinition,
    CapabilityPolicy,
    CapabilityUISchema,
)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
BUILTIN_DIR = SKILLS_DIR / "builtin"
CUSTOM_DIR = SKILLS_DIR / "custom"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

logger = logging.getLogger(__name__)

FIXED_CAPABILITIES = ["chat", "time_machine"]

# Hard-coded fixed capability definitions (not loaded from SKILL.md files).
# These are non-skill capabilities managed independently of ai_skills table:
# - chat: General Q&A handled by /chat router
# - time_machine: Pure-computation simulation handled by /time-machine router
FIXED_CAPABILITY_DEFS: list[CapabilityDefinition] = [
    CapabilityDefinition(
        id="chat",
        name="智能问答",
        description="回答关于净资产、资产配置、负债、趋势等问题",
        category="chat",
        ui=CapabilityUISchema(
            icon="message-circle",
            color="#06b6d4",
            route="/ai/chat",
            input_mode="free_text",
        ),
        policy=CapabilityPolicy(
            allowed_roles=["member", "admin"],
            enable_thinking=True,
        ),
        skill_id="chat",
    ),
    CapabilityDefinition(
        id="time_machine",
        name="资产时光机",
        description="模拟 What-if 消费场景和财务推演",
        category="simulation",
        ui=CapabilityUISchema(
            icon="clock",
            color="#a855f7",
            route="/ai/time-machine",
            input_mode="free_text",
        ),
        policy=CapabilityPolicy(
            allowed_roles=["member", "admin"],
            enable_thinking=True,
        ),
        skill_id="time_machine",
    ),
]

BUILTIN_DEFAULT_ORDER = {
    "report": 100,
    "alerts": 101,
    "allocation": 102,
    "disposal": 103,
    "liability": 104,
    "spending_leak": 105,
}


class CapabilityRegistry:
    """Loads capabilities from agent skill frontmatter."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        self._capabilities: dict[str, CapabilityDefinition] | None = None

    def list_capabilities(self) -> list[CapabilityDefinition]:
        """List all capabilities (backward compat) - merges fixed + builtin."""
        if self._capabilities is None:
            self._capabilities = self._load()
        # Merge: builtin from files + fixed hard-coded
        result = list(FIXED_CAPABILITY_DEFS)
        for cap_id, cap in self._capabilities.items():
            if cap_id not in FIXED_CAPABILITIES:  # avoid duplicate
                result.append(cap)
        return result

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        if self._capabilities is None:
            self._capabilities = self._load()
        return self._capabilities.get(capability_id)

    def list_capabilities_for_family(
        self,
        family_id: int | str,
        backend_base_url: str,
        internal_token: str,
    ) -> list[CapabilityDefinition]:
        """Merge and filter capabilities for a specific family.

        Fetches ai_skills from backend to determine enabled/disabled
        status and display order, then scans builtin + custom directories.
        """
        db_configs = self._fetch_ai_skills(family_id, backend_base_url, internal_token)
        db_map = {c["skill_id"]: c for c in db_configs}

        # Fixed capabilities (hard-coded, not from SKILL.md files)
        fixed: list[CapabilityDefinition] = list(FIXED_CAPABILITY_DEFS)

        # Builtin capabilities (filter is_enabled=false)
        builtin: list[CapabilityDefinition] = []
        for skill_dir in sorted(BUILTIN_DIR.glob("*")):
            if not skill_dir.is_dir():
                continue
            skill_id = skill_dir.name
            if skill_id in FIXED_CAPABILITIES:
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            db_record = db_map.get(skill_id)
            if db_record and not db_record.get("is_enabled", True):
                continue

            meta = self._read_frontmatter(skill_file)

            builtin.append(
                CapabilityDefinition(
                    id=skill_id,
                    name=str(meta.get("name") or skill_id),
                    description=str(meta.get("description") or ""),
                    category=str(meta.get("category") or "general"),
                    ui=CapabilityUISchema(
                        icon=str(meta.get("icon") or "message-circle"),
                        color=str(meta.get("color") or "#6366f1"),
                        route=meta.get("route") or f"/ai/{skill_id.replace('_', '-')}",
                        input_mode=str(meta.get("input_mode") or "trigger"),
                    ),
                    policy=CapabilityPolicy(
                        allowed_roles=list(meta.get("allowed_roles") or ["member", "admin"]),
                    ),
                    skill_id=skill_id,
                )
            )

        # Custom capabilities from custom/{family_id}
        custom: list[CapabilityDefinition] = []
        family_custom_dir = CUSTOM_DIR / str(family_id)
        if family_custom_dir.exists():
            for skill_dir in sorted(family_custom_dir.glob("*")):
                if not skill_dir.is_dir():
                    continue
                skill_id = skill_dir.name
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                db_record = db_map.get(skill_id)
                if db_record and not db_record.get("is_enabled", True):
                    continue

                meta = self._read_frontmatter(skill_file)
                custom.append(
                    CapabilityDefinition(
                        id=skill_id,
                        name=db_record.get("name") or str(meta.get("name") or skill_id) if db_record else str(meta.get("name") or skill_id),
                        description=db_record.get("description") or str(meta.get("description") or "") if db_record else str(meta.get("description") or ""),
                        category="custom",
                        ui=CapabilityUISchema(
                            icon=db_record.get("icon") or "star" if db_record else "star",
                            color=db_record.get("color") or "#6366f1" if db_record else "#6366f1",
                            route=None,
                            input_mode=db_record.get("input_mode") or "trigger" if db_record else "trigger",
                        ),
                        policy=CapabilityPolicy(allowed_roles=["member", "admin"]),
                        skill_id=skill_id,
                    )
                )

        return fixed + builtin + custom

    def _fetch_ai_skills(
        self,
        family_id: int | str,
        backend_base_url: str,
        internal_token: str,
    ) -> list[dict[str, Any]]:
        """Fetch ai_skills records from backend."""
        try:
            url = f"{backend_base_url.rstrip('/')}/api/v1/internal/skill-registry/{family_id}"
            resp = httpx.get(url, headers={"X-Internal-Token": internal_token}, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            logger.warning("Unexpected response type from ai_skills: %s", type(data))
            return []
        except Exception as exc:
            logger.warning("Failed to fetch ai_skills for family %s: %s", family_id, exc)
            return []

    def _load(self) -> dict[str, CapabilityDefinition]:
        """Load capabilities from builtin directory (backward compat)."""
        capabilities: dict[str, CapabilityDefinition] = {}
        builtin_dir = self.skills_dir / "builtin"
        if not builtin_dir.exists():
            # Fallback to old structure (skills/*.md)
            return self._load_legacy()

        for skill_dir in sorted(builtin_dir.glob("*")):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            capability_id = skill_dir.name
            meta = self._read_frontmatter(skill_file)
            capabilities[capability_id] = CapabilityDefinition(
                id=capability_id,
                name=str(meta.get("name") or capability_id),
                description=str(meta.get("description") or ""),
                category=str(meta.get("category") or "general"),
                ui=CapabilityUISchema(
                    icon=str(meta.get("icon") or "message-circle"),
                    color=str(meta.get("color") or "#6366f1"),
                    route=meta.get("route") or f"/ai/{capability_id.replace('_', '-')}",
                    input_mode=str(meta.get("input_mode") or "free_text"),
                    placeholder=meta.get("placeholder"),
                    example_questions=list(meta.get("examples") or meta.get("trigger_phrases") or []),
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

    def _load_legacy(self) -> dict[str, CapabilityDefinition]:
        """Fallback: load from old skills/*.md structure."""
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
