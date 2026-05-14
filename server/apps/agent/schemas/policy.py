"""Policy schemas for capability access control."""

from typing import Optional
from pydantic import BaseModel


class CapabilityPolicy(BaseModel):
    ai_enabled: bool = True
    allowed_capabilities: list[str] = []   # empty = all allowed
    admin_only_capabilities: list[str] = []
    member_role: str = "member"

    model_config = {"from_attributes": True}


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str = ""

    model_config = {"from_attributes": True}
