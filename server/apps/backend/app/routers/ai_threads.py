"""LangGraph API 安全代理路由。

拦截前端 LangGraph SDK 对 `/api/threads` 的各类请求，
注入当前用户的家庭身份信息（X-Family-Id），然后代理给后端的 Agent。
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

logger = logging.getLogger(__name__)

router = APIRouter()

# 拦截所有对 /api/threads/{path} 的 HTTP 方法
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], response_model=None)
async def proxy_langgraph_request(
    path: str,
    request: Request,
    current_user: User = Depends(require_adult),
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

    method = request.method
    agent_client = AgentClient(current_user.family_id, current_user.id)

    # 如果是流式请求 (比如 events/stream)
    if "stream" in path or request.headers.get("accept", "") == "text/event-stream":
        async def _simple_stream():
            try:
                async with agent_client.stream(
                    method,
                    f"/api/threads/{path}",
                    content=body if body else None,
                    params=params,
                    headers=forward_headers,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"LangGraph proxy stream error on {path}: {e}")
                yield b""
                
        return StreamingResponse(_simple_stream(), media_type="text/event-stream")
    else:
        # 非流式请求
        try:
            # We don't have a generic dispatch method on agent_client easily exposing content= bytes 
            # instead of json/data directly, but we can do it via a custom method or just httpx.AsyncClient usage here.
            # Actually, agent_client can expose a custom method, but we can just use httpx.AsyncClient with agent_client.headers 
            # because we need to pass raw body bytes. Wait! AgentClient's methods `post`, `get`, etc. support `data` for bytes.
            # But the HTTP method is dynamic (`method`). It's easier to just use `httpx.AsyncClient` here directly for the dynamic method 
            # while reusing the `agent_client.headers`.
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                req = client.build_request(
                    method,
                    agent_client._build_url(f"/api/threads/{path}"),
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
