"""Static UI metadata for built-in AI capabilities."""

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
    "alerts": {
        "name": "老化预警",
        "description": "即将到期资产",
        "category": "asset_health",
        "ui": {"icon": "alert-circle", "route": "/ai/alerts", "color": "#b45309"},
    },
    "allocation": {
        "name": "配置漂移",
        "description": "资产配置偏离检测",
        "category": "portfolio",
        "ui": {"icon": "radar", "route": "/ai/allocation", "color": "#7c3aed"},
    },
    "disposal": {
        "name": "闲置清仓",
        "description": "建议处置资产",
        "category": "asset_efficiency",
        "ui": {"icon": "package", "route": "/ai/disposal", "color": "#0369a1"},
    },
    "liability": {
        "name": "负债优化",
        "description": "还款策略建议",
        "category": "liability",
        "ui": {"icon": "badge-dollar-sign", "route": "/ai/liability", "color": "#be123c"},
    },
    "spending_leak": {
        "name": "资金泄漏",
        "description": "检测资金泄漏",
        "category": "asset_efficiency",
        "ui": {"icon": "shield-check", "route": "/ai/spending-leaks", "color": "#15803d"},
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
