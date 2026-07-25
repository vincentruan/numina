"""Agent 内部 Gateway API — 代理 DeerFlow Gateway 的管理端点。

供 backend 调用，通过 agent 层代理访问 DeerFlow Gateway API：
- GET  /internal/gateway/models          — 查询可用模型列表
- PUT  /internal/gateway/skills/{name}   — 更新技能启用状态
- DELETE /internal/gateway/threads/{id} — 清理线程数据
- POST /internal/gateway/skill-dispatch — 内部技能调度（skill-creator/skill-installer）

所有端点使用 X-Agent-Token 认证（与 backend 共享同一 token）。
"""

import logging
import re
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.deerflow_adapter.exceptions import DeerFlowTimeoutError
from apps.agent.services.runtime.lifespan import get_run_manager, get_stream_bridge
from apps.agent.services.runtime.sse_gateway import sse_consumer, start_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/gateway", tags=["internal"])

# Same pattern as DeerFlow's _validate_id — alphanumeric, dash, underscore only.
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

# Whitelist of internal skills that can be dispatched via this endpoint.
_ALLOWED_SKILLS = {"skill-creator", "skill-installer"}


class SkillDispatchRequest(BaseModel):
    """Request body for internal skill dispatch."""

    skill_name: str
    family_id: str
    input_text: str


def _verify_token(x_agent_token: str) -> None:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


def _validate_path_segment(value: str, label: str) -> str:
    """Validate path segment against safe ID pattern to prevent SSRF."""
    if not value or not _SAFE_ID_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}: must be alphanumeric/dash/underscore",
        )
    return value


@router.get("/models")
def list_models(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> dict:
    """查询 DeerFlow Gateway 可用模型列表。

    Returns:
        DeerFlow Gateway 返回的模型列表 JSON
    """
    _verify_token(x_agent_token)
    gateway_url = settings.DEERFLOW_GATEWAY_URL.rstrip("/")
    try:
        resp = httpx.get(f"{gateway_url}/models", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("[gateway] list_models upstream error: %s", e)
        raise HTTPException(status_code=e.response.status_code, detail=str(e)) from e
    except httpx.RequestError as e:
        logger.error("[gateway] list_models request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Gateway unreachable: {e}") from e


@router.put("/skills/{skill_name}")
def update_skill(
    skill_name: str,
    body: dict,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> dict:
    """更新 DeerFlow Gateway 技能启用状态。

    Args:
        skill_name: 技能名称（alphanumeric/dash/underscore）
        body: 技能配置 JSON（如 {"enabled": true}）

    Returns:
        DeerFlow Gateway 返回的更新结果 JSON
    """
    _verify_token(x_agent_token)
    _validate_path_segment(skill_name, "skill_name")
    gateway_url = settings.DEERFLOW_GATEWAY_URL.rstrip("/")
    try:
        resp = httpx.put(f"{gateway_url}/skills/{skill_name}", json=body, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("[gateway] update_skill upstream error skill=%s: %s", skill_name, e)
        raise HTTPException(status_code=e.response.status_code, detail=str(e)) from e
    except httpx.RequestError as e:
        logger.error("[gateway] update_skill request failed skill=%s: %s", skill_name, e)
        raise HTTPException(status_code=502, detail=f"Gateway unreachable: {e}") from e


@router.delete("/threads/{thread_id}")
def delete_thread(
    thread_id: str,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> dict:
    """清理 DeerFlow Gateway 线程数据。

    Args:
        thread_id: 线程 ID（UUID 格式，含 dash）

    Returns:
        {"success": True, "thread_id": "..."}
    """
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")
    gateway_url = settings.DEERFLOW_GATEWAY_URL.rstrip("/")
    try:
        resp = httpx.delete(f"{gateway_url}/threads/{thread_id}", timeout=10.0)
        resp.raise_for_status()
        return {"success": True, "thread_id": thread_id}
    except httpx.HTTPStatusError as e:
        logger.error("[gateway] delete_thread upstream error thread=%s: %s", thread_id, e)
        raise HTTPException(status_code=e.response.status_code, detail=str(e)) from e
    except httpx.RequestError as e:
        logger.error("[gateway] delete_thread request failed thread=%s: %s", thread_id, e)
        raise HTTPException(status_code=502, detail=f"Gateway unreachable: {e}") from e


@router.post("/skill-dispatch")
async def skill_dispatch(
    body: SkillDispatchRequest,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> dict:
    """内部技能调度端点 — 供 backend 调用内部技能（skill-creator/skill-installer）。

    # Trust: family_id is trusted because this endpoint requires X-Agent-Token
    # and the backend always passes JWT-derived current_user.family_id
    """
    _verify_token(x_agent_token)

    # Whitelist validation — only internal skills allowed
    if body.skill_name not in _ALLOWED_SKILLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid skill_name: '{body.skill_name}'. Must be one of {sorted(_ALLOWED_SKILLS)}",
        )

    # Fetch family AI config
    try:
        client = BackendClient(body.family_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid family_id: {e}") from e

    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        logger.error(
            "[gateway] skill_dispatch fetch ai_config failed family=%s: %s",
            body.family_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Failed to fetch AI config: {e}") from e

    # Construct adapter and dispatch
    try:
        adapter = create_family_adapter(
            body.family_id,
            ai_config,
            timeout_seconds=60,
        )
    except Exception as e:
        logger.error(
            "[gateway] skill_dispatch adapter creation failed family=%s: %s",
            body.family_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Adapter creation failed: {e}") from e

    context = RedactedContext(
        family_id=body.family_id,
        free_text=body.input_text,
    )
    thread_id = str(uuid4())

    try:
        result = await adapter.dispatch(body.skill_name, context, thread_id=thread_id)
    except DeerFlowTimeoutError as e:
        logger.error(
            "[gateway] skill_dispatch timeout family=%s skill=%s: %s",
            body.family_id,
            body.skill_name,
            e,
        )
        raise HTTPException(status_code=504, detail=f"DeerFlow dispatch timed out: {e}") from e
    except Exception as e:
        logger.error(
            "[gateway] skill_dispatch failed family=%s skill=%s: %s",
            body.family_id,
            body.skill_name,
            e,
        )
        raise HTTPException(status_code=502, detail=f"DeerFlow dispatch failed: {e}") from e

    return {"content": result}


class AssetReportRunRequest(BaseModel):
    """Request body for internal asset-report run trigger (backend → agent).

    The backend ``trigger_generate_events`` endpoint calls this after passing
    its own require_owner + require_ai_enabled + per-family concurrency gate.
    Trust model mirrors ``skill_dispatch``: family_id is trusted because the
    endpoint requires ``X-Agent-Token`` and the backend passes JWT-derived
    family_id (R1 internal bypass — see ``start_run(internal=True)``).
    """

    family_id: str
    user_id: str | None = None
    language: str | None = None
    input: dict[str, Any] | None = None
    on_disconnect: str = "cancel"


@router.post("/runs/asset-report/{thread_id}")
async def trigger_asset_report_run(
    thread_id: str,
    body: AssetReportRunRequest,
    request: Request,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> StreamingResponse:
    """Trigger an asset-report stream_run from the backend (service-to-service).

    U4 step 5: the backend report trigger creates a stream_run with
    ``app="asset-report"`` via this X-Agent-Token-authenticated endpoint,
    bypassing R1's frontend 409 gate (internal=True). The worker's
    ``_run_asset_report_pipeline`` then drives the 3-step pipeline and emits
    ``report.step2_json`` custom events; this endpoint streams them back as SSE
    for the backend to forward to the frontend.
    """
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")

    # Build a duck-typed body matching start_run's getattr() access pattern.
    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "asset-report", "language": body.language},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )

    record = await start_run(
        run_body,
        thread_id,
        request,
        body.family_id,
        body.user_id,
        internal=True,
    )
    run_mgr = get_run_manager(request)

    async def sse_generator():
        async for frame in sse_consumer(
            get_stream_bridge(request), record, request, run_mgr
        ):
            yield frame

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/internal/gateway/runs/asset-report/{thread_id}/{record.run_id}",
        },
    )


class FinanceCoachRunRequest(BaseModel):
    """Request body for internal finance-coach run trigger (backend → agent).

    Plan A: the backend /ai/finance-coach/generate endpoint calls this after
    passing its own require_ai_enabled + require_adult + per-family concurrency
    gate. Trust model mirrors ``AssetReportRunRequest``: family_id is trusted
    because the endpoint requires ``X-Agent-Token`` and the backend passes
    JWT-derived family_id (R1 internal bypass — see ``start_run(internal=True)``).
    """

    family_id: str
    user_id: str | None = None
    input: dict[str, Any] | None = None
    on_disconnect: str = "cancel"


@router.post("/runs/finance-coach/{thread_id}")
async def trigger_finance_coach_run(
    thread_id: str,
    body: FinanceCoachRunRequest,
    request: Request,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> StreamingResponse:
    """Trigger a finance-coach stream_run from the backend (service-to-service).

    Plan A: the backend finance-coach trigger creates a stream_run with
    ``app="finance-coach"`` via this X-Agent-Token-authenticated endpoint,
    bypassing R1's frontend 409 gate (internal=True). The worker's
    ``_run_finance_coach_agent`` then drives the single-run advice agent and
    emits a ``finance_coach.result`` custom event with the validated
    ``suggestions[]`` JSON; this endpoint streams frames back as SSE for the
    backend to forward to the frontend (D2 dashboard card).
    """
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")

    # Build a duck-typed body matching start_run's getattr() access pattern.
    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "finance-coach"},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )

    record = await start_run(
        run_body,
        thread_id,
        request,
        body.family_id,
        body.user_id,
        internal=True,
    )
    run_mgr = get_run_manager(request)

    async def sse_generator():
        async for frame in sse_consumer(
            get_stream_bridge(request), record, request, run_mgr
        ):
            yield frame

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/internal/gateway/runs/finance-coach/{thread_id}/{record.run_id}",
        },
    )


class WishAdviceRunRequest(BaseModel):
    """Request body for internal wish-advice run trigger (backend → agent).

    Plan B T7: the backend /ai/wish-advice/generate endpoint calls this after
    passing its own require_ai_enabled + require_adult + require_owner. Trust
    model mirrors ``FinanceCoachRunRequest``: family_id is trusted because the
    endpoint requires ``X-Agent-Token`` (R1 internal bypass — ``start_run(internal=True)``).
    """

    family_id: str
    user_id: str | None = None
    input: dict[str, Any] | None = None
    on_disconnect: str = "cancel"


@router.post("/runs/wish-advice/{thread_id}")
async def trigger_wish_advice_run(
    thread_id: str,
    body: WishAdviceRunRequest,
    request: Request,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> StreamingResponse:
    """Trigger a wish-advice stream_run from the backend (service-to-service).

    Plan B T7: the backend wish-advice trigger creates a stream_run with
    ``app="wish-advice"`` via this X-Agent-Token-authenticated endpoint, bypassing
    R1's frontend 409 gate (internal=True). The worker's ``_run_wish_advice_agent``
    then drives the single-run advice agent and emits a ``wish_advice.result``
    custom event with the validated ``redistribution[]`` JSON; this endpoint
    streams frames back as SSE for the backend to forward to the frontend
    (W4 WishAdviceCard).
    """
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")

    # Build a duck-typed body matching start_run's getattr() access pattern.
    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "wish-advice"},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )

    record = await start_run(
        run_body,
        thread_id,
        request,
        body.family_id,
        body.user_id,
        internal=True,
    )
    run_mgr = get_run_manager(request)

    async def sse_generator():
        async for frame in sse_consumer(
            get_stream_bridge(request), record, request, run_mgr
        ):
            yield frame

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/internal/gateway/runs/wish-advice/{thread_id}/{record.run_id}",
        },
    )
