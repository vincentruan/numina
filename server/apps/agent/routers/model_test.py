"""POST /test/model — stateless model capability test endpoint."""

import asyncio
import logging

from fastapi import APIRouter, Depends

from apps.agent.schemas.model_test import ModelTestRequest, ModelTestResult
from apps.agent.services.model_tester import (
    test_connection,
    test_thinking,
    test_vision,
    test_vision_ocr,
)
from packages.security.service_auth.agent_token_verify import verify_service_token

router = APIRouter(prefix="/test", tags=["model-test"])
logger = logging.getLogger(__name__)


@router.post("/model", response_model=ModelTestResult)
async def run_model_test(
    req: ModelTestRequest,
    _token_family: str = Depends(verify_service_token),
) -> ModelTestResult:
    """Run model capability tests with provided credentials (called by backend)."""
    vision_model = req.vision_model_id or req.model_id

    # connection always runs first — it gates the thinking test
    conn = await test_connection(req.provider, req.api_key, req.model_id, req.base_url)

    # remaining tests run in parallel
    async def _thinking():
        if "thinking" in req.test_types and conn["connected"]:
            return await test_thinking(req.provider, req.api_key, req.model_id, req.base_url)
        return None

    async def _vision():
        if "vision" in req.test_types:
            return await test_vision(req.provider, req.api_key, vision_model, req.base_url)
        return None

    async def _ocr():
        if "vision_ocr" in req.test_types:
            return await test_vision_ocr(req.provider, req.api_key, vision_model, req.base_url)
        return None

    think, vis, ocr = await asyncio.gather(_thinking(), _vision(), _ocr())

    return ModelTestResult(
        connected=conn["connected"],
        message=conn["message"],
        latency_ms=conn.get("latency_ms"),
        error_detail=conn.get("error_detail"),
        thinking_success=think["success"] if think else None,
        thinking_message=think["message"] if think else None,
        thinking_latency_ms=think.get("latency_ms") if think else None,
        vision_success=vis["success"] if vis else None,
        vision_message=vis["message"] if vis else None,
        vision_latency_ms=vis.get("latency_ms") if vis else None,
        vision_text_success=ocr["success"] if ocr else None,
        vision_text_message=ocr["message"] if ocr else None,
        vision_text_latency_ms=ocr.get("latency_ms") if ocr else None,
    )
