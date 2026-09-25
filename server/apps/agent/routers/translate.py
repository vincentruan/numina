"""Learning topic translation endpoint (called by backend proxy).

Follows the ``ai_suggest`` pattern: backend proxies via ``AgentClient``,
this router selects a provider from the family's AI config (circuit-breaker-
aware) and delegates to ``topic_translate.translate_topic()``.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.topic_translate import translate_topic
from packages.security.service_auth.agent_token_verify import verify_service_token

router = APIRouter(prefix="/translate", tags=["translate"])
logger = logging.getLogger(__name__)


class TranslateTopicRequest(BaseModel):
    name: str
    description: str = ""
    evidence: list[str] = []
    assessment_prompt: str = ""


@router.post("/topic")
async def translate_topic_endpoint(
    body: TranslateTopicRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    _token_family: str = Depends(verify_service_token),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """Translate a learning topic to Chinese using the family's AI provider."""
    client = BackendClient(family_id=x_family_id)
    ai_config = await client.get_family_ai_config()
    providers = ai_config.get("providers", [])
    if not providers:
        raise HTTPException(status_code=503, detail="No AI provider configured")

    # Circuit-state aware selection
    from apps.agent.services.orchestrator import _select_stream_run_provider

    selected = _select_stream_run_provider(providers)
    if selected is None:
        raise HTTPException(status_code=503, detail="All AI providers unavailable")

    topic_dict = body.model_dump()
    try:
        return await translate_topic(topic_dict, selected)
    except ValueError as e:
        logger.warning("Translation failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        logger.exception("Translation LLM call failed")
        raise HTTPException(status_code=503, detail="Translation service unavailable")
