"""Static UI metadata overrides for AI capabilities surfaced by ``/ai/capabilities``.

Each key is a capability id; values are display overrides applied on top of the
agent's CapabilityDefinition (or on top of the fallback dict when the agent is
unreachable). The backend has the final say on user-facing display names, so
the agent's ``FIXED_CAPABILITY_DEFS`` and skill frontmatter are starting points,
not authoritative for the UI.

The set of keys here is broader than ``BUILTIN_CAPABILITIES`` from ``ai_skills``:

- ``chat`` and ``time_machine`` are routing capabilities (not skills — they don't
  appear in skill management). They are exposed by ``/ai/capabilities`` and listed
  in ``_ROUTING_CAPABILITIES`` (see ``ai_capabilities``). Their entries here carry
  the canonical display name the frontend renders for the chat input chip and
  the resolveable ``/ai/chat`` and ``/ai/time-machine`` routes.
- ``report`` is the business skill from ``BUILTIN_CAPABILITIES``. It doubles as a
  capability (routable detail page) and a skill (toggleable in skill management).
- The 5 外扩 trigger capabilities (alerts/allocation/disposal/liability/spending_leak)
  were removed in U7; their analysis regressed to numina SOUL (chat/SKILL.md).

This dict has no agent-association fields. The brainstorm/plan reference to
"capability_catalog agent associations" found no such fields to remove (per
feasibility review of the plan); see plan U3 deviation note.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_CAPABILITY_OVERRIDES: dict[str, dict[str, Any]] = {
    "report": {
        "name": "资产体检",
        "description": "综合健康评分",
        "category": "asset_health",
        "ui": {"icon": "activity", "route": "/ai/report", "color": "#6366f1"},
    },
    "chat": {
        "name": "AI 问答",
        "description": "自由对话助手",
        "category": "conversation",
        "ui": {
            "icon": "message-circle",
            "route": "/ai/chat",
            "color": "#0f766e",
            "placeholder": "问我任何关于家庭资产的问题…",
            "example_questions": ["我们家净资产是多少？", "有哪些资产需要关注？"],
        },
    },
    "time_machine": {
        "name": "资产时光机",
        "description": "What-if 模拟、财务推演",
        "category": "simulation",
        "ui": {"icon": "clock", "route": "/ai/time-machine", "color": "#4338ca"},
    },
}


def apply_capability_overrides(capability: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(capability)
    override = _CAPABILITY_OVERRIDES.get(result["id"], {})
    result.update({k: v for k, v in override.items() if k != "ui"})
    ui = result.setdefault("ui", {})
    ui.update(override.get("ui", {}))
    return result
