"""输入润色端点代理路由 — 转发给 agent 服务。

前端 composer 调用 ``/api/input-polish``，由后端代理转发给 agent 的
``/input-polish``。

为何走后端代理：prod nginx 只有 backend upstream（无 agent upstream），
``/api`` 前缀在 dev（Vite proxy）与 prod（nginx → backend）都路由到 backend，
故由 backend 收口转发。

鉴权：agent 的 ``/input-polish`` 用 ``verify_family_token`` 校验 **JWT**
（从 ``Authorization: Bearer`` 或 ``access_token`` cookie 读取），不接受
``X-Agent-Token``。``AgentClient`` 只注入内部 token，因此本代理额外从请求中
取出浏览器的 JWT，作为 ``Authorization`` 头与 ``access_token`` cookie 透传给
agent，使其通过 ``verify_family_token``。同时仍由 backend 的
``require_adult`` + ``require_ai_enabled`` 做前置鉴权。
"""

import logging

import httpx
from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import ACCESS_TOKEN_COOKIE, require_adult
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

router = APIRouter(prefix="/api", tags=["ai-input-polish"])
logger = logging.getLogger(__name__)


class InputPolishRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    locale: str | None = None
    thread_id: str | None = None


@router.post("/input-polish")
async def input_polish(
    body: InputPolishRequest,
    request: Request,
    current_user: User = Depends(require_adult),
    access_token: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    _ai: None = Depends(require_ai_enabled),
):
    """代理转发给 agent 的输入润色接口，返回改写后的草稿。

    返回裸 ``JSONResponse``（不经 EnvelopeResponse 包装），与前端
    ``polishInputDraft`` 直接读 ``rewritten_text`` / ``changed`` 的契约一致。
    """
    # JWT 来源：优先 Authorization Bearer，回退 access_token cookie
    jwt_token: str | None = None
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization[7:]
    if not jwt_token:
        jwt_token = access_token
    if not jwt_token:
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    forward_headers: dict[str, str] = {}
    if jwt_token:
        # verify_family_token 优先读 Authorization，cookie 作为兜底
        forward_headers["Authorization"] = f"Bearer {jwt_token}"
        forward_headers["Cookie"] = f"{ACCESS_TOKEN_COOKIE}={jwt_token}"

    try:
        agent_client = AgentClient(current_user.family_id, current_user.id, timeout=45.0)
        resp = await agent_client.post(
            "/input-polish",
            json=body.model_dump(),
            headers=forward_headers,
        )
        resp.raise_for_status()
        return JSONResponse(content=resp.json())
    except httpx.TimeoutException:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT) from None
    except Exception as e:
        logger.error(f"调用 agent input-polish 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from None
