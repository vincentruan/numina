"""Agent 内部 Gateway API — 代理 DeerFlow Gateway 的管理端点。

供 backend 调用，通过 agent 层代理访问 DeerFlow Gateway API：
- GET  /internal/gateway/models          — 查询可用模型列表
- PUT  /internal/gateway/skills/{name}   — 更新技能启用状态
- DELETE /internal/gateway/threads/{id} — 清理线程数据

所有端点使用 X-Agent-Token 认证（与 backend 共享同一 token）。
"""

import logging
import re

import httpx
from fastapi import APIRouter, Header, HTTPException

from apps.agent.app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/gateway", tags=["internal"])

# Same pattern as DeerFlow's _validate_id — alphanumeric, dash, underscore only.
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


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
