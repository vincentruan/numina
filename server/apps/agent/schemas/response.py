"""AgentResponse domain schema — stable output contract for all agent capabilities."""

import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field


class Scorecard(BaseModel):
    name: str
    score: float
    max_score: float = 5.0
    label: str = ""
    color: str = ""  # e.g. "green", "yellow", "red"

    model_config = {"from_attributes": True}


class RiskFlag(BaseModel):
    level: str  # "high", "medium", "low"
    title: str
    description: str = ""

    model_config = {"from_attributes": True}


class Recommendation(BaseModel):
    priority: str = "medium"  # "high", "medium", "low"
    title: str
    body: str = ""
    action_type: str = "suggestion"  # "suggestion", "confirmation_needed", "info"

    model_config = {"from_attributes": True}


class Finding(BaseModel):
    source: str  # "rule" or "ai"
    content: str
    confidence: float = 1.0  # 0.0-1.0

    model_config = {"from_attributes": True}


class UIBlock(BaseModel):
    block_type: str  # "scorecard_grid", "risk_list", "recommendation_list", "text"
    data: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class ConfirmationItem(BaseModel):
    item_id: str
    description: str
    suggested_action: str = ""

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    capability: str
    summary: str = ""
    scorecards: list[Scorecard] = []
    risk_flags: list[RiskFlag] = []
    recommendations: list[Recommendation] = []
    followup_actions: list[Recommendation] = []
    disclaimers: list[str] = []
    ui_blocks: list[UIBlock] = []
    needs_confirmation: list[ConfirmationItem] = []
    rule_based_findings: list[Finding] = []
    ai_inferences: list[Finding] = []
    fallback_used: bool = False
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    model_config = {"from_attributes": True}
