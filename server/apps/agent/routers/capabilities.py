"""Agent capability discovery routes."""

from fastapi import APIRouter, Header, HTTPException

from apps.agent.app.config import settings
from apps.agent.schemas.capability import CapabilityDefinition
from apps.agent.services.capability_registry import capability_registry

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", response_model=list[CapabilityDefinition])
def list_capabilities(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> list[CapabilityDefinition]:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
    return capability_registry.list_capabilities()
