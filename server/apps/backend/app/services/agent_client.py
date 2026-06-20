"""Unified HTTP client for communicating with the Agent microservice."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from apps.backend.app.config import settings

logger = logging.getLogger(__name__)

class AgentClient:
    """A wrapper around httpx.AsyncClient that injects Numina tenant isolation headers.
    
    Automatically handles constructing the URL with AGENT_BASE_URL and injects
    X-Family-Id, X-User-Id, and X-Agent-Token for secure tenant boundary enforcement.
    """

    def __init__(self, family_id: int | str, user_id: int | str | None = None, timeout: float | httpx.Timeout = 30.0):
        self.family_id = str(family_id)
        self.user_id = str(user_id) if user_id is not None else None
        
        # Build base headers
        self.headers = {
            "X-Family-Id": self.family_id,
            "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
        }
        if self.user_id:
            self.headers["X-User-Id"] = self.user_id

        # Use a more resilient timeout configuration for LLM requests if not explicitly overridden
        if isinstance(timeout, (int, float)):
            self.timeout = httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=5.0)
        else:
            self.timeout = timeout

    def _build_url(self, endpoint: str) -> str:
        """Prepend AGENT_BASE_URL if endpoint is a relative path."""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        # Ensure smooth concatenation
        base = settings.AGENT_BASE_URL.rstrip("/")
        path = endpoint.lstrip("/")
        return f"{base}/{path}"

    async def get(self, endpoint: str, params: dict[str, Any] | None = None, **kwargs) -> httpx.Response:
        """Send a GET request to the agent."""
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return await client.get(self._build_url(endpoint), params=params, headers=headers, **kwargs)

    async def post(self, endpoint: str, json: Any = None, data: Any = None, **kwargs) -> httpx.Response:
        """Send a POST request to the agent."""
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return await client.post(self._build_url(endpoint), json=json, data=data, headers=headers, **kwargs)

    async def patch(self, endpoint: str, json: Any = None, data: Any = None, **kwargs) -> httpx.Response:
        """Send a PATCH request to the agent."""
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return await client.patch(self._build_url(endpoint), json=json, data=data, headers=headers, **kwargs)

    async def delete(self, endpoint: str, params: dict[str, Any] | None = None, **kwargs) -> httpx.Response:
        """Send a DELETE request to the agent."""
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return await client.delete(self._build_url(endpoint), params=params, headers=headers, **kwargs)

    @asynccontextmanager
    async def stream(self, method: str, endpoint: str, **kwargs) -> AsyncGenerator[httpx.Response, None]:
        """Context manager for streaming requests (e.g. SSE or NDJSON)."""
        headers = {**self.headers, **kwargs.pop("headers", {})}
        # Long read timeout for streaming LLM responses
        stream_timeout = httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)

        async with httpx.AsyncClient(timeout=stream_timeout, trust_env=False) as client:
            req = client.build_request(
                method, 
                self._build_url(endpoint), 
                headers=headers, 
                **kwargs
            )
            async with client.stream(req.method, req.url, content=req.content, headers=req.headers) as resp:
                yield resp

