"""LangGraph API 安全代理路由。

拦截前端 LangGraph SDK 对 `/api/threads` 的各类请求，
注入当前用户的家庭身份信息（X-Family-Id），然后代理给后端的 Agent。
"""

import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

logger = logging.getLogger(__name__)

router = APIRouter()


async def _proxy_to_agent(
    path: str,
    request: Request,
    current_user: User,
) -> Response | StreamingResponse:
    """代理转发 LangGraph SDK 的请求到 Agent 端。

    安全机制: 附加 X-Family-Id 等关键头信息，实现租户级别数据隔离。
    """
    # 读取请求的 body 和 params
    body = await request.body()
    params = dict(request.query_params)

    # 透传需要的请求头 (排除 host, content-length 等由 httpx 自动处理的)
    forward_headers = {}
    for h in ["content-type", "accept"]:
        if h in request.headers:
            forward_headers[h] = request.headers[h]

    # 转发用户的 access token，以便 agent 端的 verify_family_token 能通过 JWT 认证。
    # AgentClient 只发送 X-Agent-Token (service token)，但 agent 的 threads 端点
    # 需要 Authorization: Bearer <access_token> 或 access_token cookie。
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        forward_headers["authorization"] = auth_header
    else:
        access_cookie = request.cookies.get("access_token")
        if access_cookie:
            forward_headers["authorization"] = f"Bearer {access_cookie}"

    method = request.method
    agent_client = AgentClient(current_user.family_id, current_user.id)
    target_path = f"/api/threads/{path}" if path else "/api/threads"

    # 如果是流式请求 (比如 events/stream)
    if (path and "stream" in path) or request.headers.get("accept", "") == "text/event-stream":
        async def _simple_stream():
            try:
                async with agent_client.stream(
                    method,
                    target_path,
                    content=body if body else None,
                    params=params,
                    headers=forward_headers,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                        if await request.is_disconnected():
                            logger.info(f"LangGraph proxy stream client disconnected path={path}")
                            break
            except Exception as e:
                logger.error(f"LangGraph proxy stream error on {path}: {e}")
                yield b""

        return StreamingResponse(_simple_stream(), media_type="text/event-stream")
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                req = client.build_request(
                    method,
                    agent_client._build_url(target_path),
                    content=body if body else None,
                    params=params,
                    headers={**agent_client.headers, **forward_headers},
                )
                resp = await client.send(req)
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers={k: v for k, v in resp.headers.items() if k.lower() not in ("content-length", "content-encoding", "transfer-encoding", "connection")},
                    media_type=resp.headers.get("content-type"),
                )
        except httpx.TimeoutException:
            logger.error(f"LangGraph proxy timeout on {path}")
            return Response(content="Gateway Timeout", status_code=504)
        except Exception as e:
            logger.error(f"LangGraph proxy error on {path}: {e}")
            return Response(content="Internal Server Error", status_code=500)


# 拦截 /api/threads 根路径 (如 POST /api/threads 创建线程)
@router.api_route("", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], response_model=None)
async def proxy_langgraph_root(
    request: Request,
    current_user: User = Depends(require_adult),
) -> Response | StreamingResponse:
    """代理转发 /api/threads 根路径请求到 Agent 端。"""
    return await _proxy_to_agent("", request, current_user)


# 拦截所有对 /api/threads/{path} 的 HTTP 方法
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], response_model=None)
async def proxy_langgraph_request(
    path: str,
    request: Request,
    current_user: User = Depends(require_adult),
) -> Response | StreamingResponse:
    """代理转发 LangGraph SDK 的请求到 Agent 端。"""
    return await _proxy_to_agent(path, request, current_user)
