"""家庭财务上下文数据模型（脱敏前后）。"""

from typing import Any

from pydantic import BaseModel


class FamilyContext(BaseModel):
    """从 backend 拉取的家庭原始数据容器。"""

    family_id: str
    assets: list[dict[str, Any]] = []
    liabilities: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    dashboard_overview: dict[str, Any] = {}
    dashboard_allocation: dict[str, Any] = {}
    dashboard_trend: dict[str, Any] = {}
    low_usage_assets: list[dict[str, Any]] = []
    free_text: str | None = None  # 用于 chat 端点的用户自由文本输入

    model_config = {"from_attributes": True}


class RedactedContext(BaseModel):
    """脱敏后的家庭数据容器，可安全传入 LLM。"""

    family_id: str
    assets: list[dict[str, Any]] = []
    liabilities: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    dashboard_overview: dict[str, Any] = {}
    dashboard_allocation: dict[str, Any] = {}
    dashboard_trend: dict[str, Any] = {}
    low_usage_assets: list[dict[str, Any]] = []
    free_text: str | None = None  # 已脱敏的自由文本（或 None）
    redaction_log: list[str] = []    # 记录被脱敏的字段，用于审计，不发送给 LLM

    model_config = {"from_attributes": True}
